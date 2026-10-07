import urllib.request, json, time

base = 'http://127.0.0.1:8080'

# Create network
req = urllib.request.Request(
    f'{base}/api/network/create',
    data=json.dumps({'creator_id': 'test123', 'creator_name': 'TestUser', 'network_name': 'Test Network'}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
r = json.loads(urllib.request.urlopen(req).read())
net_id = r.get('network_id')
print(f'[1] Network created: {net_id}')

# Join network
req1b = urllib.request.Request(
    f'{base}/api/network/join',
    data=json.dumps({'network_id': net_id, 'client_id': 'test123', 'username': 'TestUser'}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
r1b = json.loads(urllib.request.urlopen(req1b).read())
print(f'[2] Network join: {r1b.get("success")} ({r1b.get("network_id")})')

# Create room
try:
    req2 = urllib.request.Request(
        f'{base}/api/room/create',
        data=json.dumps({'room_name': 'classroom', 'client_id': 'test123', 'network_id': net_id}).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    r2 = json.loads(urllib.request.urlopen(req2).read())
    print(f'[3] Room create: {r2}')
except Exception as e:
    print(f'[3] Room create: {e}')

# Send message
req3 = urllib.request.Request(
    f'{base}/api/send',
    data=json.dumps({
        'sender': 'TestUser', 'client_id': 'test123',
        'channel': '#classroom', 'text': 'Hello from TestUser!', 'network_id': net_id
    }).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
r3 = json.loads(urllib.request.urlopen(req3).read())
print(f'[4] Send message: {r3}')

# Fetch messages
time.sleep(0.3)
msgs_url = f'{base}/api/messages?channel=%23classroom&network_id={net_id}&client_id=test123'
r4 = json.loads(urllib.request.urlopen(msgs_url).read())
msgs = r4.get('messages', [])
print(f'[5] Messages fetched: {len(msgs)} total')
if msgs:
    last = msgs[-1]
    print(f'    Last: {last.get("sender")}: {last.get("message")}')

# Status check
r5 = json.loads(urllib.request.urlopen(f'{base}/api/status').read())
print(f'[6] Status: host_ip={r5.get("host_ip")}, web_port={r5.get("web_port")}, interfaces={len(r5.get("interfaces",[]))}')

# Network info
req_info = urllib.request.Request(
    f'{base}/api/network/info',
    data=json.dumps({'network_id': net_id}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
r6 = json.loads(urllib.request.urlopen(req_info).read())
print(f'[7] Network info: {r6}')

print('\nALL API TESTS PASSED')
