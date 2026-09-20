import io,json,os,unittest
from unittest.mock import patch
from browser_collector import extract
class BrowserCollectorTests(unittest.TestCase):
    def request(self):return {'fields':['名称','链接'],'page':{'url':'https://example.com/catalog','text':'A public product','links':[]}}
    def test_invalid_or_challenged_snapshot_never_calls_model(self):
        for change in [{'fields':[]},{'fields':['x','x']},{'page':{'url':'file:///secret','text':'x'}},{'page':{'url':'https://example.com','text':'x','blocked':True}}]:
            with patch('browser_collector.urlopen') as api:
                body,status=extract(dict(self.request(),**change));self.assertEqual(status,400);api.assert_not_called()
    def test_structured_rows_and_no_url_fetch(self):
        result={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps({'rows':[{'名称':'A','链接':'https://example.com/a'}],'warning':''})}]}]}
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch('browser_collector.urlopen',return_value=io.StringIO(json.dumps(result))) as api:
            body,status=extract(self.request());self.assertEqual(status,200);self.assertEqual(len(body['rows']),1)
            request=api.call_args.args[0];self.assertEqual(request.full_url,'https://api.openai.com/v1/responses')
            sent=json.loads(request.data);self.assertFalse(sent['store']);self.assertTrue(sent['text']['format']['strict'])
    def test_incomplete_model_output_is_not_success(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch('browser_collector.urlopen',return_value=io.StringIO('{"status":"incomplete"}')):
            self.assertEqual(extract(self.request())[1],502)
if __name__=='__main__':unittest.main()
