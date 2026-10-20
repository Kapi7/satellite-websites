import copy
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import reviewed_publisher as pub
import require_article_hero

class ReviewedPublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.item=copy.deepcopy(json.loads(pub.MANIFEST.read_text())['articles'][0])
        real=pub.article_path(self.item,'en');self.path=self.root/real.relative_to(pub.ROOT)
        self.path.parent.mkdir(parents=True)
        self.path.write_text(re.sub(r"^draft:.*$", "draft: true", real.read_text(), flags=re.M))
        for image in self.item['locales']['en']['images']:
            rel=Path(self.item['site'])/'public'/image.lstrip('/')
            (self.root/rel).parent.mkdir(parents=True,exist_ok=True);(self.root/rel).write_bytes((pub.ROOT/rel).read_bytes())
        self.patch=patch.object(pub,'ROOT',self.root);self.patch.start()
        self.hero=patch.object(require_article_hero,'ROOT',self.root);self.hero.start()
    def tearDown(self):
        self.hero.stop();self.patch.stop();self.temp.cleanup()
    def test_reviewed_english_bundle_does_not_require_unreviewed_languages(self):
        self.assertEqual(pub.validate(self.item),[])
    def test_changed_copy_invalidates_approval(self):
        self.path.write_text(self.path.read_text()+'\nUnreviewed claim.\n')
        self.assertTrue(any('copy changed' in e for e in pub.validate(self.item)))
    def test_changed_photo_invalidates_approval(self):
        image=next(iter(self.item['locales']['en']['images']))
        (self.root/self.item['site']/'public'/image.lstrip('/')).write_bytes(b'changed')
        self.assertTrue(any('image changed' in e for e in pub.validate(self.item)))
    def test_missing_hero_blocks(self):
        image=next(iter(self.item['locales']['en']['images']))
        (self.root/self.item['site']/'public'/image.lstrip('/')).unlink()
        self.assertTrue(any('missing' in e for e in pub.validate(self.item)))
    def test_excluded_translation_is_untouched(self):
        other=pub.article_path(self.item,'es');other.parent.mkdir();other.write_text(self.path.read_text())
        before=other.read_bytes();pub.prepare(self.item)
        self.assertEqual(other.read_bytes(),before)
        self.assertIn('draft: false',self.path.read_text())
        self.assertEqual(pub.validate(self.item),[])
    def test_excluded_public_translation_fails(self):
        other=pub.article_path(self.item,'es');other.parent.mkdir();other.write_text(self.path.read_text().replace('draft: true','draft: false'))
        self.assertTrue(any('unreviewed translation' in e for e in pub.validate(self.item)))
    def test_retry_keeps_content_and_date(self):
        pub.prepare(self.item);before=self.path.read_bytes();pub.prepare(self.item)
        self.assertEqual(self.path.read_bytes(),before)
    def test_photo_verification_uses_explicit_verifier_headers(self):
        host=pub.SITES[self.item['site']][1]
        html=(' '.join(self.item['liveMarkers'])+' https://'+host+'/'+self.item['slug']+'/').encode()
        image=next(iter(self.item['locales']['en']['images']))
        image_bytes=(self.root/self.item['site']/'public'/image.lstrip('/')).read_bytes()
        calls=[]
        def response(request, timeout):
            calls.append(request)
            self.assertEqual(request.get_header('User-agent'),'SatelliteReleaseVerifier/1.0')
            return io.BytesIO(image_bytes if '/images/' in request.full_url else html)
        with patch.object(pub.urllib.request,'urlopen',side_effect=response):pub.verify_live(self.item)
        self.assertEqual(len(calls),2)

    def test_no_notification_or_generation_in_release_entrypoint(self):
        text=(Path(__file__).parent/'daily-publish.sh').read_text()
        self.assertIn('DISABLE_OUTBOUND_NOTIFICATIONS=1',text)
        self.assertNotIn('translate-content',text);self.assertNotIn('refill_queue',text)

if __name__=='__main__':unittest.main()
