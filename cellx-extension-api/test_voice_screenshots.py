import base64
from io import BytesIO
import json
import unittest
from unittest.mock import patch
from voice_screenshots import image_content, analyze_screenshots

IMAGE = 'data:image/png;base64,' + base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode()


class ScreenshotsTest(unittest.TestCase):
    def test_validation(self):
        self.assertEqual(image_content([]), [])
        self.assertEqual(image_content([IMAGE])[0]['type'], 'input_image')
        for value in ['bad', [IMAGE]*4, ['https://example.com/private'], ['data:image/png;base64,!'], ['data:image/png;base64,aGVsbG8=']]:
            with self.assertRaises(ValueError): image_content(value)

    def test_no_files(self):
        self.assertEqual(analyze_screenshots({})[1],400)
        self.assertEqual(analyze_screenshots([])[1],400)

    @patch.dict('os.environ', {'OPENAI_API_KEY':'test-only'})
    def test_multimodal_request(self):
        def open_request(request, timeout):
            data=json.loads(request.data)
            self.assertFalse(data['store'])
            self.assertEqual(data['input'][0]['content'][1]['image_url'],IMAGE)
            return BytesIO(json.dumps({'output':[{'content':[{'type':'output_text','text':'Image analysis'}]}]}).encode())
        with patch('voice_screenshots.urlopen',side_effect=open_request):
            body,status=analyze_screenshots({'prompt':'What is wrong?','screenshots':[IMAGE]})
        self.assertEqual(status,200)
        self.assertEqual(body['analysis'],'Image analysis')

    @patch.dict('os.environ', {'OPENAI_API_KEY':'test-only'})
    def test_builder_images(self):
        import server
        def open_request(request,timeout):
            data=json.loads(request.data)
            self.assertEqual(data['input'][0]['content'][1]['image_url'],IMAGE)
            text=json.dumps({'nodes':[],'links':[]})
            return BytesIO(json.dumps({'output':[{'content':[{'type':'output_text','text':text}]}]}).encode())
        with patch.object(server,'urlopen',side_effect=open_request):
            body,status=server.ai_workflow_builder({'prompt':'Create a workflow','screenshots':[IMAGE]})
        self.assertEqual(status,200)
        self.assertTrue(body['ok'])


if __name__ == '__main__': unittest.main()
