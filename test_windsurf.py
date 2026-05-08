"""Test Windsurf gRPC via Python h2. Fixed HTTP/2 handshake."""
import socket, ssl, struct, time, uuid

PORT = 60423
CSRF = 'aafc3a6e-9b0b-4345-9f23-831a44e8f380'
API_KEY = 'test-key'

# ─── Proto helpers ───
def _v(v):
    parts = []
    while v > 0x7F: parts.append((v & 0x7F) | 0x80); v >>= 7
    parts.append(v & 0x7F)
    return bytes(parts) if parts else b'\x00'

def _t(f, w): return _v((f << 3) | w)
def _wf(f, v): return _t(f, 0) + _v(v)
def _ws(f, s): d = s.encode('utf8'); return _t(f, 2) + _v(len(d)) + d if s else b''
def _wm(f, b): return _t(f, 2) + _v(len(b)) + b if b else b''

def _read_varint(buf, pos):
    r, s = 0, 0
    while pos < len(buf):
        b = buf[pos]; pos += 1
        r |= (b & 0x7F) << s
        if not (b & 0x80): break
        s += 7
    return r, pos

def _parse(buf):
    fs, p = [], 0
    while p < len(buf):
        tv, p = _read_varint(buf, p)
        fn, wt = tv >> 3, tv & 7
        if wt == 0: val, p = _read_varint(buf, p); fs.append((fn, wt, val))
        elif wt == 2: ln, p = _read_varint(buf, p); fs.append((fn, wt, buf[p:p+ln])); p += ln
        else: break
    return fs

def _gf(fs, n, w=None):
    for fn, wt, v in fs:
        if fn == n and (w is None or wt == w): return v
    return None

def _build_metadata(api_key):
    sid = str(uuid.uuid4())
    return (_ws(1, 'windsurf') + _ws(2, '1.9600.41') + _ws(3, api_key) +
            _ws(4, 'en') + _ws(5, 'windows') + _ws(7, '1.9600.41') +
            _ws(8, 'x86_64') + _wf(9, int(time.time()*1000)) + _ws(10, sid) + _ws(12, 'windsurf'))

def _build_cascade_config():
    conv = _wf(4, 3)  # NO_TOOL
    comm = _wf(1, 1) + _ws(2, 'You are a conversational AI assistant. Answer directly.')
    conv += _wm(13, comm)
    conversational = _wm(2, conv)
    plc = conversational
    brain = _wf(1, 1) + _wm(6, _wm(6, b''))
    return _wm(1, plc) + _wm(7, brain)

# ─── gRPC frame ───
def grpc_frame(payload):
    return b'\x00' + struct.pack('>I', len(payload)) + payload

def strip_frame(buf):
    if len(buf) >= 5 and buf[0] == 0:
        ml = struct.unpack('>I', buf[1:5])[0]
        if len(buf) >= 5 + ml: return buf[5:5+ml]
    return buf

# ─── HTTP/2 frames ───
def h2_settings_frame(ack=False):
    flags = 0x01 if ack else 0x00
    return struct.pack('>I', 0)[:3] + b'\x04' + bytes([flags, 0, 0, 0, 0])

def h2_headers_frame(stream_id, headers, end_stream=False):
    hp = b''
    for k, v in headers:
        hp += _v(0x10) + _v(len(k)) + k.encode() + _v(len(v)) + v.encode()
    flags = 0x04  # END_HEADERS
    if end_stream: flags |= 0x01
    sid = struct.pack('>I', stream_id)
    return struct.pack('>I', len(hp))[:3] + b'\x01' + bytes([flags]) + sid[1:] + hp

def h2_data_frame(stream_id, data, end_stream=True):
    flags = 0x01 if end_stream else 0x00
    sid = struct.pack('>I', stream_id)
    return struct.pack('>I', len(data))[:3] + b'\x00' + bytes([flags]) + sid[1:] + data

def read_frame(sock):
    """Read one HTTP/2 frame."""
    header = b''
    while len(header) < 9:
        chunk = sock.recv(9 - len(header))
        if not chunk: return None
        header += chunk
    length = (header[0] << 16) | (header[1] << 8) | header[2]
    ftype = header[3]
    flags = header[4]
    sid = struct.unpack('>I', b'\x00' + header[5:9])[0]
    payload = b''
    while len(payload) < length:
        chunk = sock.recv(length - len(payload))
        if not chunk: break
        payload += chunk
    return (ftype, flags, sid, payload)

# ─── gRPC call ───
def grpc_call(path, body):
    sock = socket.create_connection(('127.0.0.1', PORT), timeout=30)

    # 1. Connection preface
    sock.sendall(b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n')

    # 2. Client SETTINGS (empty)
    sock.sendall(h2_settings_frame(ack=False))

    # 3. Read server SETTINGS and ACK it
    while True:
        f = read_frame(sock)
        if not f: break
        ftype, flags, sid, payload = f
        if ftype == 4 and sid == 0:  # SETTINGS
            sock.sendall(h2_settings_frame(ack=True))
        if ftype == 4 and flags & 0x01:  # SETTINGS ACK
            break

    # 4. Send HEADERS frame
    headers = [
        (':method', 'POST'), (':path', path), (':scheme', 'http'),
        (':authority', f'localhost:{PORT}'),
        ('content-type', 'application/grpc'),
        ('te', 'trailers'),
        ('x-codeium-csrf-token', CSRF),
    ]
    sock.sendall(h2_headers_frame(1, headers))

    # 5. Send DATA frame with gRPC body
    sock.sendall(h2_data_frame(1, grpc_frame(body)))

    # 6. Read response
    response = b''
    sock.settimeout(30)
    while True:
        try:
            f = read_frame(sock)
            if not f: break
            ftype, flags, sid, payload = f
            if ftype == 0 and sid == 1:  # DATA
                response += payload
            if ftype == 0 and flags & 0x01:  # END_STREAM
                break
        except socket.timeout:
            break
    sock.close()
    return strip_frame(response)

# ─── Test ───
print("Testing Windsurf gRPC...")

# StartCascade
meta = _build_metadata(API_KEY)
req = _wm(1, meta)
resp = grpc_call('/exa.language_server_pb.LanguageServerService/StartCascade', req)
fs = _parse(resp)
cid = _gf(fs, 1)
if isinstance(cid, bytes): cid = cid.decode()
print(f"Cascade ID: {cid}")

# Send message
text = 'Say hi in one word'
msg = (_ws(1, cid) + _wm(2, _ws(1, text)) +
       _wm(3, _build_metadata(API_KEY)) + _wm(5, _build_cascade_config()))
grpc_call('/exa.language_server_pb.LanguageServerService/SendUserCascadeMessage', msg)
print("Message sent, polling...")

# Poll
for i in range(30):
    poll = _ws(1, cid)
    resp = grpc_call('/exa.language_server_pb.LanguageServerService/GetCascadeTrajectorySteps', poll)
    fs = _parse(resp)
    for fn, wt, v in fs:
        if fn == 1 and wt == 2:
            sf = _parse(v)
            planner = _gf(sf, 20)
            if planner and isinstance(planner, bytes):
                pf = _parse(planner)
                text_b = _gf(pf, 8) or _gf(pf, 1)
                if isinstance(text_b, bytes):
                    result = text_b.decode()
                    print(f"Response ({i}s): {result[:300]}")
                    exit()
    time.sleep(1)

print("Timeout")
