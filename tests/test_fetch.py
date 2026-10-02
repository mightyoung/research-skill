import gzip,importlib.util,io,json,tarfile,tempfile,unittest,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PDF=b'%PDF-1.4\nfixture objects\n%%EOF\n'
def archive(entries=None):
 out=io.BytesIO()
 with tarfile.open(fileobj=out,mode='w:gz') as t:
  for name,body,kind in entries or [('main.tex',b'New result % old comment\n\\% retained\n','file'),('main.tex.orig',b'Obsolete result','file'),('old/main.tex',b'Old result','file')]:
   info=tarfile.TarInfo(name)
   if kind=='file': info.size=len(body);t.addfile(info,io.BytesIO(body))
   elif kind=='link': info.type=tarfile.SYMTYPE;info.linkname='../../outside';t.addfile(info)
   elif kind=='hardlink': info.type=tarfile.LNKTYPE;info.linkname='main.tex';t.addfile(info)
   elif kind=='device':info.type=tarfile.CHRTYPE;t.addfile(info)
 return out.getvalue()
class Response(io.BytesIO):
 def __init__(self,body,ctype='application/octet-stream',length=None,status=200,url=None):
  super().__init__(body);self.status=status;self.headers={'Content-Type':ctype,'Content-Length':str(len(body) if length is None else length)};self.url=url
 def geturl(self):return self.url
class Fixture:
 def __init__(self,pdf=PDF,source=None):self.pdf=pdf;self.source=archive() if source is None else source;self.calls=[];self.failures={}
 def __call__(self,request,timeout):
  url=request.full_url;self.calls.append(url)
  if url in self.failures:
   count=self.failures[url]
   if count: self.failures[url]-=1;raise urllib.error.HTTPError(url,503,'fixture',{},None)
  value=self.pdf if '/pdf/' in url else self.source
  if isinstance(value,BaseException):raise value
  if callable(value):return value(url)
  return Response(value,'application/pdf' if '/pdf/' in url else 'application/octet-stream',url=url)
class FetchTests(unittest.TestCase):
 def setUp(self):
  p=ROOT/'scripts/fetch_paper.py';self.assertTrue(p.exists(),'new downloader missing')
  spec=importlib.util.spec_from_file_location('fetch_paper',p);self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name)
 def fetch(self,fixture,id='2301.11305v1',slug='fixture'):
  return self.m.fetch(id,slug,self.root,opener=fixture,pause=lambda _:None)
 def test_versioned_atomic_raw_clean_repeat(self):
  f=Fixture();path=self.fetch(f);self.assertEqual((path/'paper.pdf').read_bytes(),PDF)
  self.assertIn(b'% old comment',(path/'source/raw/main.tex').read_bytes());self.assertNotIn(b'old comment',(path/'source/clean/main.tex').read_bytes())
  self.assertIn(b'New result',(path/'source/clean/main.tex').read_bytes());self.assertNotIn(b'Obsolete',(path/'source/clean/main.tex').read_bytes())
  self.assertFalse((path/'source/clean/old').exists());self.assertFalse((path/'source/clean/main.tex.orig').exists())
  before={str(p.relative_to(path)):p.read_bytes() for p in path.rglob('*') if p.is_file()};count=len(f.calls)
  self.assertEqual(self.fetch(f),path);self.assertEqual(len(f.calls),count)
  self.assertEqual(before,{str(p.relative_to(path)):p.read_bytes() for p in path.rglob('*') if p.is_file()})
 def test_new_version_separate_same_pdf_source_id(self):
  f=Fixture();p1=self.fetch(f);p2=self.fetch(f,'2301.11305v2');self.assertNotEqual(p1,p2);self.assertTrue(p1.exists())
  self.assertTrue(any('/pdf/2301.11305v2' in x for x in f.calls));self.assertTrue(any('/e-print/2301.11305v2' in x for x in f.calls))
 def test_unpinned_id_and_unsafe_slug_rejected(self):
  for id,slug in [('2301.11305','fixture'),('2301.11305v1','../escape'),('2301.11305v0','fixture')]:
   with self.assertRaises(ValueError):self.fetch(Fixture(),id,slug)
 def test_pdf_404_html_truncation_leave_previous_untouched(self):
  p=self.fetch(Fixture());before=(p/'paper.pdf').read_bytes()
  values=[urllib.error.HTTPError('https://arxiv.org/pdf/x',404,'missing',{},None),b'<html>not a PDF</html>',b'%PDF-1.4 truncated',lambda u:Response(PDF,length=len(PDF)+10,url=u)]
  for value in values:
   with self.assertRaises((ValueError,urllib.error.URLError,OSError)):self.fetch(Fixture(pdf=value),'2301.11305v2')
   self.assertFalse((p.parent/'v2').exists());self.assertEqual((p/'paper.pdf').read_bytes(),before)
   self.assertFalse(list(p.parent.glob('.stage-*')))
 def test_source_missing_explicit_pdf_only(self):
  f=Fixture(source=urllib.error.HTTPError('https://arxiv.org/e-print/x',404,'missing',{},None));p=self.fetch(f)
  self.assertEqual(json.loads((p/'manifest.json').read_text())['source_status'],'PDF-only');self.assertFalse((p/'source').exists())
 def test_bounded_retry_and_transient_source_failure(self):
  f=Fixture();f.failures['https://arxiv.org/pdf/2301.11305v1']=2;self.fetch(f);self.assertEqual(f.calls.count('https://arxiv.org/pdf/2301.11305v1'),3)
  f=Fixture();f.failures['https://arxiv.org/e-print/2301.11305v2']=10
  with self.assertRaises(urllib.error.HTTPError):self.fetch(f,'2301.11305v2')
  self.assertEqual(f.calls.count('https://arxiv.org/e-print/2301.11305v2'),3)
  self.assertFalse((self.root/'related_work/fixture/versions/v2').exists())
 def test_malicious_archives_abort_without_contaminating_old(self):
  p=self.fetch(Fixture());before=(p/'source/raw/main.tex').read_bytes()
  for name,kind in [('../outside','file'),('/outside','file'),('link','link'),('hard','hardlink'),('dev','device'),('a\\b','file')]:
   with self.assertRaises(ValueError):self.fetch(Fixture(source=archive([(name,b'evil',kind)])),'2301.11305v2')
   self.assertFalse((p.parent/'v2').exists());self.assertEqual((p/'source/raw/main.tex').read_bytes(),before)
 def test_archive_limits_duplicates_and_html(self):
  for source in [archive([('main.tex',b'a','file'),('./main.tex',b'b','file')]),b'<html>error</html>',archive([('big.tex',b'x'*100,'file')])]:
   self.m.MAX_EXPANDED=50
   with self.assertRaises(ValueError):self.fetch(Fixture(source=source))
  self.assertFalse((self.root/'related_work/fixture/versions/v1').exists())
 def test_gzip_single_tex_supported(self):
  p=self.fetch(Fixture(source=gzip.compress(b'\\documentclass{article}\nNew % old\n')));self.assertTrue((p/'source/raw/main.tex').exists())
 def test_version_redirect_refused(self):
  f=Fixture(pdf=lambda u:Response(PDF,'application/pdf',url='https://arxiv.org/pdf/2301.11305v2'))
  with self.assertRaises(ValueError):self.fetch(f)
 def test_interruption_preserves_old_and_cleans_stage(self):
  p=self.fetch(Fixture());f=Fixture(source=KeyboardInterrupt())
  with self.assertRaises(KeyboardInterrupt):self.fetch(f,'2301.11305v2')
  self.assertTrue(p.exists());self.assertFalse((p.parent/'v2').exists());self.assertFalse(list(p.parent.glob('.stage-*')))
 def test_cache_tamper_refused_and_symlink_target_refused(self):
  p=self.fetch(Fixture());(p/'paper.pdf').write_bytes(b'bad')
  with self.assertRaises(ValueError):self.fetch(Fixture())
  t=self.root/'other';t.mkdir();(t/'related_work').symlink_to(self.root/'related_work')
  with self.assertRaises(ValueError):self.m.fetch('2301.11305v2','fixture',t,opener=Fixture(),pause=lambda _:None)

 def test_source_pdf_fallback_is_explicit(self):
  p=self.fetch(Fixture(source=PDF));self.assertEqual(json.loads((p/'manifest.json').read_text())['source_status'],'PDF-only')
 def test_member_count_and_http_size_limits(self):
  self.m.MAX_FILES=1
  with self.assertRaises(ValueError):self.fetch(Fixture())
  self.m.MAX_DOWNLOAD=10
  with self.assertRaises(ValueError):self.fetch(Fixture())
 def test_compressed_metadata_bomb_bounded_before_tar_parse(self):
  self.m.MAX_EXPANDED=100
  with self.assertRaises(ValueError):self.fetch(Fixture(source=gzip.compress(b'x'*10000)))
