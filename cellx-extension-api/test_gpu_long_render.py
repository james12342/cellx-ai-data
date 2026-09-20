import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import gpu_storyboard_render as renderer

class LongRenderTests(unittest.TestCase):
    def test_300_seconds_does_not_allow_a_long_presenter(self):
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder);photo=run/'source.png';Image.new('RGB',(20,20)).save(photo)
            job={'photo_ids':['p','r'],'options':{'voice':'zh-male','duration_seconds':300,'scenes':[{'photo_id':'p','narration':'Opening'},{'photo_id':'r','narration':'Rest'}]}}
            calls=[]
            with patch.object(renderer,'probe',side_effect=[21.,279.]):
                with self.assertRaises(renderer.StoryboardTimingError) as error:renderer.render(job,run,'python',lambda args,*a,**kw:calls.append(args),lambda i:photo,{})
            self.assertEqual(error.exception.timing['opening_seconds'],21.)
            self.assertFalse(any('inference.py' in c for c in calls))

    def test_long_subtitle_cues_are_bounded_and_cover_entire_interval(self):
        text='窗边可以看到庭院中的树木。明亮的墙面与深色地板形成对比。'*15
        cues=renderer.split_cues([(240.,299.9,text)],50)
        self.assertGreater(len(cues),15);self.assertEqual(cues[0][0],240.);self.assertEqual(cues[-1][1],299.9)
        self.assertEqual(''.join(c[2] for c in cues),text)
        self.assertTrue(all(sum(2 if ord(c)>=0x2e80 else 1 for c in t)<=50 for _,_,t in cues))

if __name__=='__main__':unittest.main()
