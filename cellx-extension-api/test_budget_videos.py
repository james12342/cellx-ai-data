import json
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import budget_videos as budget
import runway_videos as runway
import promo_videos as promo


class BudgetTests(unittest.TestCase):
    def payload(self, model, duration):
        return dict(request_id='a'*40, photo_ids=['b'*40], confirm_paid=True,
                    approved_credits=budget.price(model, duration),
                    options=dict(mode='runway', model=model, duration_seconds=duration,
                                 product_info='Blue cup', concept='', style='studio', aspect_ratio='9:16'))

    def test_all_prices_and_validation(self):
        for model, duration, cents in [('wan_turbo',5,10),('hailuo_fast',6,19),('hailuo_fast',10,32),('kling_turbo',10,70),('gen4_turbo',5,25)]:
            payload=self.payload(model,duration)
            self.assertEqual(budget.price(model,duration),cents)
            self.assertEqual(runway.validate(payload)['model'],model)
            payload['options']['audio']=True
            with self.assertRaises(ValueError): runway.validate(payload)
        for model,duration in [('hailuo_fast',5),('kling_turbo',6),('gen4_turbo',12),('wan_turbo',10)]:
            payload=self.payload('product_ad',10);payload['options'].update(model=model,duration_seconds=duration)
            with self.assertRaises(ValueError): runway.validate(payload)

    def test_missing_key_and_price_tampering(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'FAL_KEY':''}):
            root=Path(folder);payload=self.payload('wan_turbo',5)
            self.assertEqual(runway.start(root,payload)[1],503)
            with patch.dict(os.environ, {'FAL_KEY':'test-only'}):
                payload['approved_credits']=1
                self.assertEqual(runway.start(root,payload)[1],400)
            self.assertEqual(list(root.iterdir()),[])

    def test_queue_persists_and_resumes_without_resubmit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);job=dict(id='a'*40,options=runway.validate(self.payload('wan_turbo',5)))
            receipt=dict(request_id='task-123',status_url='https://queue.fal.run/fal-ai/wan/requests/task-123/status',response_url='https://queue.fal.run/fal-ai/wan/requests/task-123')
            result={'video':{'url':'https://v3.fal.media/test.mp4'}}
            with patch.object(budget,'fal_request',side_effect=[receipt,{'status':'COMPLETED'},result]) as call:
                self.assertEqual(budget.fal_task(root,job,[{'uri':'data:image/png;base64,fixture'}])['id'],'task-123')
                self.assertNotIn('duration',call.call_args_list[0].args[1])
            saved=json.loads((root/('a'*40+'.json')).read_text())
            self.assertEqual(saved['task_id'],'task-123')
            with patch.object(budget,'fal_request',side_effect=[{'status':'COMPLETED'},result]) as call:
                budget.fal_task(root,saved,[])
                self.assertTrue(all(len(c.args)==1 for c in call.call_args_list))

    def test_fal_submission_timeout_never_resubmits(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);job=dict(id='a'*40,provider='fal',options=runway.validate(self.payload('wan_turbo',5)))
            with patch.object(runway,'fal_task',side_effect=TimeoutError):runway.submit(root,job,[])
            self.assertEqual(job['status'],'needs_review')

    def test_cdn_and_queue_url_rejection(self):
        for url in ['http://queue.fal.run/fal-ai/test','https://queue.fal.run.evil.com/fal-ai/test','https://evil.com/video.mp4']:
            with self.assertRaises(ValueError): budget.fal_request(url)
        with self.assertRaises(ValueError):runway.download('https://evil.com/a.mp4',Path('unused.mp4'))

    def test_turbo_sdk_payload(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        client=MagicMock()
        with patch.dict(sys.modules, {'runwayml':SimpleNamespace(RunwayML=MagicMock(return_value=client))}):
            runway.product_ad_task(runway.validate(self.payload('gen4_turbo',5)),[{'uri':'data:image/png;base64,fixture'}])
        kwargs=client.image_to_video.create.call_args.kwargs
        self.assertEqual(kwargs['model'],'gen4_turbo');self.assertEqual(kwargs['ratio'],'720:1280')
        client.image_to_video.create.return_value.wait_for_task_output.assert_called_once()


if __name__=='__main__': unittest.main()
