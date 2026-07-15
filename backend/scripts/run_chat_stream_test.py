import requests, json, time
BASE = 'http://127.0.0.1:8000'
PIN = '1234'

def get_token():
    r = requests.post(f'{BASE}/api/v1/auth/pin', json={'pin': PIN}, timeout=10)
    r.raise_for_status()
    return r.json().get('access_token')


def stream_chat(token, message='Explain the primary differences between supervised learning, unsupervised learning, and reinforcement learning in detail.'):
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'text/event-stream', 'Content-Type': 'application/json'}
    r = requests.post(f'{BASE}/api/v1/chat/stream', headers=headers, json={'message': message}, stream=True, timeout=120)
    print('status', r.status_code, 'content-type', r.headers.get('content-type'))
    collected = ''
    start = time.time()
    if r.status_code==200:
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            print('LINE:', line)
            if line.startswith('data:'):
                payload = line[5:].strip()
                if payload == '[DONE]':
                    break
                try:
                    data = json.loads(payload)
                    if data.get('delta'):
                        collected += data['delta']
                    elif data.get('done'):
                        print('DONE', data)
                except Exception as e:
                    print('parse error', e, payload)
    else:
        print('error', r.text)
    duration = time.time() - start
    print('Collected length', len(collected), 'duration', duration)
    print('Full text:\n', collected[:2000])
    return collected

if __name__=='__main__':
    tok = get_token()
    txt = stream_chat(tok)
    print('\n---END---')
