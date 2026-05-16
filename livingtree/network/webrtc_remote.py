"""WebRTC Remote Ops — P2P remote control of server via WebRTC DataChannel.

Browser ↔ Server direct P2P connection for:
- Remote terminal (shell execution with real-time output)
- File browser (list/read/write server filesystem)
- System monitor (CPU/memory/disk/processes, pushed every 2s)
- Service management (start/stop/restart services)
- Log streaming (tail -f over data channel)

Uses WebRTC DataChannel for low-latency, encrypted, bidirectional communication.
Signaling via existing /ws WebSocket. No extra ports needed after connection.

Protocol: JSON messages over DataChannel
  → {"op":"shell","cmd":"ls -la","cwd":"/home"}
  ← {"op":"shell_result","exit":0,"stdout":"...","stderr":"..."}
  → {"op":"monitor","interval":2}
  ← {"op":"monitor_data","cpu":45.2,"mem":62.1,"disk":78.3,...}
  → {"op":"file_list","path":"/var/log"}
  ← {"op":"file_list_result","files":[...]}
  → {"op":"file_read","path":"/var/log/syslog","lines":100}
  ← {"op":"file_read_result","content":"..."}
"""

from __future__ import annotations

import asyncio
import json as _json
import os
import platform
import time as _time
from pathlib import Path
from typing import Any, Optional

from loguru import logger
import psutil

IS_WINDOWS = platform.system() == "Windows"


class RemoteOpsSession:
    """One WebRTC data channel session for remote operations."""

    def __init__(self, session_id: str, channel: Any):
        self.session_id = session_id
        self._channel = channel
        self._monitor_task: Optional[asyncio.Task] = None
        self._shell_processes: dict[str, asyncio.subprocess.Process] = {}
        self._cwd = str(Path.cwd())
        self._connected_at = _time.time()

    async def handle_message(self, data: str):
        """Dispatch incoming DataChannel messages."""
        try:
            msg = _json.loads(data)
        except Exception:
            return
        op = msg.get("op", "")

        if op == "shell":
            await self._handle_shell(msg)
        elif op == "shell_kill":
            await self._handle_shell_kill(msg)
        elif op == "monitor_start":
            await self._handle_monitor_start(msg)
        elif op == "monitor_stop":
            await self._handle_monitor_stop()
        elif op == "file_list":
            await self._handle_file_list(msg)
        elif op == "file_read":
            await self._handle_file_read(msg)
        elif op == "file_write":
            await self._handle_file_write(msg)
        elif op == "cd":
            await self._handle_cd(msg)
        elif op == "ping":
            self._send({"op": "pong", "uptime": _time.time() - self._connected_at})

    def _send(self, data: dict):
        try:
            self._channel.send(_json.dumps(data, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"RemoteOps send error: {e}")

    # ── Shell ──

    async def _handle_shell(self, msg: dict):
        cmd = msg.get("cmd", msg.get("command", ""))
        cwd = msg.get("cwd", self._cwd)
        timeout = msg.get("timeout", 30)

        if not cmd.strip():
            self._send({"op": "shell_result", "request_id": msg.get("request_id", ""), "exit": -1, "stderr": "empty command"})
            return

        from ..core.shell_env import get_shell
        shell = get_shell()
        result = await shell.execute(cmd, workdir=cwd, timeout=timeout)
        self._send({
            "op": "shell_result",
            "request_id": msg.get("request_id", ""),
            "exit": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "elapsed_ms": result.elapsed_ms,
            "blocked": result.blocked,
        })

    async def _handle_shell_kill(self, msg: dict):
        pid = msg.get("pid", 0)
        proc = self._shell_processes.pop(str(pid), None)
        if proc:
            try:
                proc.kill()
            except Exception:
                pass

    # ── System Monitor ──

    async def _handle_monitor_start(self, msg: dict):
        interval = msg.get("interval", 2)
        if self._monitor_task:
            self._monitor_task.cancel()
        self._monitor_task = asyncio.create_task(self._monitor_loop(interval))

    async def _handle_monitor_stop(self):
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None

    async def _monitor_loop(self, interval: float):
        while True:
            data = {"op": "monitor_data", "ts": _time.time()}
            if psutil is not None:
                data["cpu"] = round(psutil.cpu_percent(interval=0.5), 1)
                mem = psutil.virtual_memory()
                data["mem"] = round(mem.percent, 1)
                data["mem_used_gb"] = round(mem.used / (1024**3), 1)
                data["mem_total_gb"] = round(mem.total / (1024**3), 1)
                disk = psutil.disk_usage("/")
                data["disk"] = round(disk.percent, 1)
                data["disk_free_gb"] = round(disk.free / (1024**3), 1)
                data["net_sent_mb"] = round(psutil.net_io_counters().bytes_sent / (1024**2), 1)
                data["net_recv_mb"] = round(psutil.net_io_counters().bytes_recv / (1024**2), 1)
                procs = []
                for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                    try:
                        pi = p.info
                        if pi.get('cpu_percent', 0) > 0.5 or pi.get('memory_percent', 0) > 1:
                            procs.append(pi)
                    except Exception:
                        pass
                data["top_processes"] = sorted(procs, key=lambda x: x.get('cpu_percent', 0), reverse=True)[:5]
            else:
                data["cpu"] = 0
                data["mem"] = 0
                data["disk"] = 0
                data["error"] = "psutil not installed"
            self._send(data)
            await asyncio.sleep(interval)

    # ── File Operations ──

    async def _handle_file_list(self, msg: dict):
        path_str = msg.get("path", self._cwd)
        p = Path(path_str)
        if not p.exists():
            self._send({"op": "file_list_result", "request_id": msg.get("request_id", ""), "error": "path not found", "path": path_str})
            return
        try:
            files = []
            for entry in sorted(p.iterdir())[:200]:
                try:
                    st = entry.stat()
                    files.append({
                        "name": entry.name,
                        "type": "dir" if entry.is_dir() else "file",
                        "size": st.st_size,
                        "modified": st.st_mtime,
                    })
                except PermissionError:
                    files.append({"name": entry.name, "type": "locked"})
            self._send({
                "op": "file_list_result",
                "request_id": msg.get("request_id", ""),
                "path": str(p.resolve()),
                "files": files,
            })
        except Exception as e:
            self._send({"op": "file_list_result", "request_id": msg.get("request_id", ""), "error": str(e)})

    async def _handle_file_read(self, msg: dict):
        path_str = msg.get("path", "")
        max_lines = msg.get("lines", 200)
        max_bytes = msg.get("max_bytes", 100000)

        from ..core.shell_env import ChunkedFileReader
        try:
            reader = ChunkedFileReader(path_str)
            content = reader.head(max_lines)[:max_bytes]
            self._send({
                "op": "file_read_result",
                "request_id": msg.get("request_id", ""),
                "path": path_str,
                "content": content,
                "size": reader.size,
                "size_mb": round(reader.size_mb, 2),
                "truncated": len(content) >= max_bytes,
            })
        except FileNotFoundError:
            self._send({"op": "file_read_result", "request_id": msg.get("request_id", ""), "error": "not found", "path": path_str})
        except Exception as e:
            self._send({"op": "file_read_result", "request_id": msg.get("request_id", ""), "error": str(e)})

    async def _handle_file_write(self, msg: dict):
        path_str = msg.get("path", "")
        content = msg.get("content", "")
        if not path_str:
            return
        try:
            Path(path_str).write_text(content, encoding="utf-8")
            self._send({"op": "file_write_result", "request_id": msg.get("request_id", ""), "ok": True, "path": path_str})
        except Exception as e:
            self._send({"op": "file_write_result", "request_id": msg.get("request_id", ""), "error": str(e)})

    async def _handle_cd(self, msg: dict):
        new_path = msg.get("path", self._cwd)
        p = Path(new_path)
        if p.exists() and p.is_dir():
            self._cwd = str(p.resolve())
        self._send({"op": "cd_result", "cwd": self._cwd})

    def close(self):
        if self._monitor_task:
            self._monitor_task.cancel()
        for proc in self._shell_processes.values():
            try:
                proc.kill()
            except Exception:
                pass


class WebRTCRemoteHub:
    """Manages WebRTC remote ops sessions."""

    def __init__(self):
        self._sessions: dict[str, RemoteOpsSession] = {}

    def create_session(self, session_id: str, channel) -> RemoteOpsSession:
        session = RemoteOpsSession(session_id, channel)
        self._sessions[session_id] = session
        logger.info(f"RemoteOps session started: {session_id}")
        return session

    def close_session(self, session_id: str):
        s = self._sessions.pop(session_id, None)
        if s:
            s.close()

    def status(self) -> dict:
        return {
            "active_sessions": len(self._sessions),
            "sessions": [
                {"id": sid, "uptime": round(_time.time() - s._connected_at)}
                for sid, s in self._sessions.items()
            ],
        }


_remote_hub: Optional[WebRTCRemoteHub] = None


def get_remote_hub() -> WebRTCRemoteHub:
    global _remote_hub
    if _remote_hub is None:
        _remote_hub = WebRTCRemoteHub()
    return _remote_hub


# ═══ Client-side JavaScript (included in panel HTML) ═══

WEBRTC_REMOTE_JS = r"""
var _rtcPc=null,_rtcDc=null,_rtcMonitorActive=false,_rtcReqId=0;

function rtcConnect(){
  _rtcPc=new RTCPeerConnection({iceServers:[{urls:'stun:stun.l.google.com:19302'}]});
  _rtcDc=_rtcPc.createDataChannel('remote-ops',{ordered:true});
  _rtcDc.onopen=function(){document.getElementById('rtc-status').innerHTML='<span style=color:var(--accent)>● P2P已连接</span>';_rtcPing()};
  _rtcDc.onmessage=function(e){rtcOnMsg(JSON.parse(e.data))};
  _rtcDc.onclose=function(){document.getElementById('rtc-status').innerHTML='<span style=color:var(--err)>● P2P断开</span>'};
  _rtcPc.onicecandidate=function(e){if(e.candidate)rtcSendSignal({ice:e.candidate})};
  _rtcPc.createOffer().then(function(o){_rtcPc.setLocalDescription(o);rtcSendSignal({sdp:o})});
}
function rtcSendSignal(sig){
  var ws=new WebSocket((location.protocol==='https:'?'wss:':'ws:')+location.host+'/ws/rtc-signal');
  ws.onopen=function(){ws.send(JSON.stringify(sig))};
  ws.onmessage=function(e){
    var d=JSON.parse(e.data);
    if(d.sdp)_rtcPc.setRemoteDescription(new RTCSessionDescription(d.sdp));
    if(d.ice)_rtcPc.addIceCandidate(new RTCIceCandidate(d.ice));
  };
}
function rtcSend(op,data){if(_rtcDc&&_rtcDc.readyState==='open'){_rtcReqId++;data.request_id='r'+_rtcReqId;data.op=op;_rtcDc.send(JSON.stringify(data))}}
function rtcOnMsg(d){
  if(d.op==='pong')return;
  if(d.op==='shell_result'){var out=document.getElementById('rtc-shell-out');out.innerHTML='<pre style=font-size:11px;white-space:pre-wrap;max-height:300px;overflow-y:auto>'+d.stdout+d.stderr+'</pre>'}
  if(d.op==='monitor_data'){document.getElementById('rtc-cpu').textContent=d.cpu+'%';document.getElementById('rtc-mem').textContent=d.mem+'%';document.getElementById('rtc-disk').textContent=d.disk+'%'}
  if(d.op==='file_list_result'){var el=document.getElementById('rtc-file-list');el.innerHTML=d.files?d.files.map(function(f){return'<div style=padding:2px_0;cursor:pointer;font-size:11px onclick=rtcSend(\"file_read\",{path:\"'+d.path+'/'+f.name+'\"})>'+'📁'[f.type==='file'?'📄'.charCodeAt(0):0]+' '+f.name+' <span style=color:var(--dim);font-size:9px>'+(f.size?Math.round(f.size/1024)+'KB':'')+'</span></div>'}).join(''):'error'}
  if(d.op==='file_read_result'){document.getElementById('rtc-file-content').textContent=d.content||d.error}
}
function rtcShell(){var c=document.getElementById('rtc-shell-cmd').value.trim();if(c)rtcSend('shell',{cmd:c})}
function rtcMonitor(){_rtcMonitorActive=!_rtcMonitorActive;rtcSend(_rtcMonitorActive?'monitor_start':'monitor_stop',{interval:2});document.getElementById('rtc-monitor-btn').textContent=_rtcMonitorActive?'⏸ 停止':'▶ 监控'}
function rtcFileBrowse(){rtcSend('file_list',{path:document.getElementById('rtc-file-path').value||'.'})}
function _rtcPing(){setInterval(function(){rtcSend('ping',{})},10000)}
"""
