"""Windsurf gRPC client — Python implementation of WindsurfAPI.
Communicates with local language_server_windows_x64 via HTTP/2 gRPC.
Zero external deps: uses built-in h2 + socket.
"""
import socket, ssl, struct, time, json, uuid

# ─── Proto helpers ───
def _varint(v):
    """Encode unsigned integer as varint bytes."""
    if v < 0: v = v & 0xFFFFFFFFFFFFFFFF
    parts = []
    while v > 0x7F:
        parts.append((v & 0x7F) | 0x80)
        v >>= 7
    parts.append(v & 0x7F)
    return bytes(parts) if parts else b'\x00'

def _tag(field, wire):
    return _varint((field << 3) | wire)

def _w_varint(field, value):
    return _tag(field, 0) + _varint(value)

def _w_string(field, s):
    if not s: return b''
    data = s.encode('utf-8')
    return _tag(field, 2) + _varint(len(data)) + data

def _w_message(field, buf):
    if not buf: return b''
    return _tag(field, 2) + _varint(len(buf)) + buf

def _w_bool(field, v):
    return _w_varint(field, 1) if v else b''

# ─── Proto parser ───
def _parse(buf):
    fields, pos = [], 0
    while pos < len(buf):
        tag_v, pos = _read_varint(buf, pos)
        fn, wt = tag_v >> 3, tag_v & 7
        if wt == 0:
            val, pos = _read_varint(buf, pos)
            fields.append((fn, wt, val))
        elif wt == 2:
            ln, pos = _read_varint(buf, pos)
            fields.append((fn, wt, buf[pos:pos+ln]))
            pos += ln
        else:
            break
    return fields

def _read_varint(buf, pos):
    result, shift = 0, 0
    while pos < len(buf):
        b = buf[pos]; pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80): break
        shift += 7
    return result, pos

def _get_field(fields, num, wt=None):
    for fn, w, v in fields:
        if fn == num and (wt is None or w == wt):
            return v
    return None

# ─── gRPC frame ───
def _grpc_frame(payload):
    return b'\x00' + struct.pack('>I', len(payload)) + payload

def _strip_frame(buf):
    if len(buf) >= 5 and buf[0] == 0:
        ml = struct.unpack('>I', buf[1:5])[0]
        if len(buf) >= 5 + ml:
            return buf[5:5+ml]
    return buf

# ─── Timestamp ───
def _encode_ts():
    now = int(time.time() * 1000)
    secs, nanos = now // 1000, (now % 1000) * 1_000_000
    return _w_varint(1, secs) + (_w_varint(2, nanos) if nanos else b'')

# ─── Metadata ───
def _build_metadata(api_key, session_id=None):
    sid = session_id or str(uuid.uuid4())
    return (
        _w_string(1, 'windsurf') +
        _w_string(2, '1.9600.41') +
        _w_string(3, api_key) +
        _w_string(4, 'en') +
        _w_string(5, 'windows') +
        _w_string(7, '1.9600.41') +
        _w_string(8, 'x86_64') +
        _w_varint(9, int(time.time() * 1000)) +
        _w_string(10, sid) +
        _w_string(12, 'windsurf')
    )

# ─── Cascade config ───
def _build_cascade_config(model_uid=None, model_enum=None):
    # CascadeConversationalPlannerConfig: planner_mode=3 (NO_TOOL)
    conv = _w_varint(4, 3)  # NO_TOOL
    # Communication section override
    comm = (
        _w_varint(1, 1) +  # OVERRIDE
        _w_string(2, 'You are a conversational AI assistant. Answer directly.')
    )
    conv += _w_message(13, comm)
    conversational = _w_message(2, conv)

    planner = [conversational]
    if model_uid:
        planner.append(_w_string(35, model_uid))
        planner.append(_w_string(34, model_uid))
    if model_enum and model_enum > 0:
        planner.append(_w_message(15, _w_varint(1, model_enum)))

    planner_config = b''.join(planner)
    brain = _w_varint(1, 1) + _w_message(6, _w_message(6, b''))
    return _w_message(1, planner_config) + _w_message(7, brain)

# ─── HTTP/2 gRPC call ───
def _grpc_call(port, csrf_token, path, body, timeout=30):
    """Make unary gRPC call via raw HTTP/2."""
    import ssl as _ssl

    ctx = _ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = _ssl.CERT_NONE

    sock = socket.create_connection(('127.0.0.1', port), timeout=timeout)

    # HTTP/2 connection preface
    sock.sendall(b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n')

    # Settings frame (empty)
    settings = b'\x00\x00\x00\x04\x00\x00\x00\x00\x00'
    sock.sendall(settings)

    # Build HEADERS frame
    headers = [
        (':method', 'POST'), (':path', path), (':scheme', 'http'),
        (':authority', f'localhost:{port}'),
        ('content-type', 'application/grpc'),
        ('te', 'trailers'),
        ('x-codeium-csrf-token', csrf_token),
    ]
    hp = b''
    for k, v in headers:
        hp += _varint(0x10)  # never indexed
        hp += _varint(len(k)) + k.encode()
        hp += _varint(len(v)) + v.encode()

    # HEADERS frame: stream_id=1, flags=END_HEADERS(4)+END_STREAM(1)=5 for no body, or 4
    frame = struct.pack('>I', len(hp))[:3] + b'\x01\x04' + hp
    sock.sendall(frame)

    # DATA frame with gRPC body
    frame_body = _grpc_frame(body)
    data_frame = struct.pack('>I', len(frame_body))[:3] + b'\x00\x01' + frame_body
    sock.sendall(data_frame)

    # Read response
    response = b''
    sock.settimeout(timeout)
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if len(response) > 1024 * 1024:
                break
    except socket.timeout:
        pass
    sock.close()

    # Parse HTTP/2 frames (simplified: skip preface and settings frames, find DATA)
    return _parse_h2_response(response)

def _parse_h2_response(data):
    """Extract payload from HTTP/2 response frames."""
    # Skip SETTINGS ACK (type 4) and other non-DATA frames
    pos = 0
    result = b''
    while pos + 9 <= len(data):
        length = (data[pos] << 16) | (data[pos+1] << 8) | data[pos+2]
        frame_type = data[pos+3]
        flags = data[pos+4]
        stream_id = struct.unpack('>I', b'\x00' + data[pos+5:pos+9])[0]
        pos += 9
        if frame_type == 0 and stream_id == 1:  # DATA frame
            result += data[pos:pos+length]
        elif frame_type == 1:  # HEADERS frame
            pass  # skip
        pos += length
    return _strip_frame(result)

# ─── High-level API ───
class WindsurfAPI:
    def __init__(self, port, api_key, csrf_token):
        self.port = port
        self.api_key = api_key
        self.csrf_token = csrf_token

    def _call(self, service, method, body):
        path = f'/exa.language_server_pb.LanguageServerService/{method}'
        return _grpc_call(self.port, self.csrf_token, path, body)

    def chat(self, messages, model_uid=None, model_enum=None):
        """Send chat messages and return response text."""
        # StartCascade
        meta = _build_metadata(self.api_key)
        req = _w_message(1, meta)
        resp = self._call('LanguageServerService', 'StartCascade', req)
        fields = _parse(resp)
        cascade_id = _get_field(fields, 1)
        if isinstance(cascade_id, bytes):
            cascade_id = cascade_id.decode('utf-8')

        # SendUserCascadeMessage
        text = messages[-1].get('content', '') if messages else 'Hello'
        msg_body = (
            _w_string(1, cascade_id) +
            _w_message(2, _w_string(1, text)) +
            _w_message(3, _build_metadata(self.api_key)) +
            _w_message(5, _build_cascade_config(model_uid, model_enum))
        )
        self._call('LanguageServerService', 'SendUserCascadeMessage', msg_body)

        # Poll GetCascadeTrajectorySteps
        for _ in range(60):
            poll_body = _w_string(1, cascade_id)
            resp = self._call('LanguageServerService', 'GetCascadeTrajectorySteps', poll_body)
            fields = _parse(resp)
            # Find planner_response text
            steps = [v for fn, wt, v in fields if fn == 1 and wt == 2]
            for step_buf in steps:
                sf = _parse(step_buf)
                # type=15 = PLANNER_RESPONSE
                step_type = _get_field(sf, 1)
                planner = _get_field(sf, 20)
                if planner and isinstance(planner, bytes):
                    pf = _parse(planner)
                    response_text = _get_field(pf, 1)
                    modified_text = _get_field(pf, 8)
                    text = modified_text or response_text
                    if isinstance(text, bytes):
                        text = text.decode('utf-8')
                    if text:
                        return text
            time.sleep(1)
        return '[Timeout]'
