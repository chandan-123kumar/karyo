import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from trace_viewer import load_sessions, make_server
from token_usage import TokenUsage
from contextlib import redirect_stderr
from io import StringIO


class ViewerTests(unittest.TestCase):
    def test_pending_completion_and_partial_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'session.jsonl'
            tracker = TokenUsage(path, include_content=True)
            request = {'model': 'test', 'messages': [{'role': 'user', 'content': '<script>alert(1)</script>'}]}
            tracker.start(request)
            session = load_sessions(directory)['sessions'][0]
            self.assertEqual(session['calls'][0]['status'], 'pending')
            with redirect_stderr(StringIO()):
                tracker.record({'choices': []}, request=request)
            with path.open('a') as stream:
                stream.write('{unfinished')
            result = load_sessions(directory)
            self.assertEqual(len(result['sessions'][0]['calls']), 1)
            self.assertEqual(result['sessions'][0]['calls'][0]['status'], 'ok')
            self.assertEqual(result['skipped'], 1)

    def test_server_requires_secret_and_correct_host(self):
        with tempfile.TemporaryDirectory() as directory:
            server, url = make_server(directory)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(url, timeout=5) as response:
                    self.assertIn(b'Trace explorer', response.read())
                    self.assertEqual(response.headers['Cache-Control'], 'no-store')
                with urlopen(url + 'api/sessions', timeout=5) as response:
                    self.assertEqual(json.load(response)['sessions'], [])
                for request in [url.rsplit('/', 2)[0] + '/', Request(url, headers={'Host': 'attacker.test'}), url+'../secret']:
                    with self.assertRaises(HTTPError):
                        urlopen(request, timeout=5)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
