"""Offline tests for locally authored acquisition code; never external code."""
import hashlib
import importlib.util
import io
import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
DOI = '10.1234/example'
XML = b'<article><front><article-meta><article-title>Fixture</article-title></article-meta></front><body><sec><title>Methods</title><p>' + b'research evidence ' * 30 + b'</p></sec></body></article>'
PDF = b'%PDF-1.4\n1 0 obj<</Type /Catalog>>endobj\n2 0 obj<</Type /Page>>endobj\nxref\n0 1\n0000000000 65535 f\ntrailer<</Root 1 0 R>>\nstartxref\n80\n%%EOF\n'

class Fixtures:
    def __init__(self, rows): self.rows = rows; self.calls = []
    def json(self, url):
        self.calls.append(url)
        value = self.rows[len(self.calls)-1]
        if isinstance(value, BaseException): raise value
        return value
    def get(self, url, limit=None):
        self.calls.append(url)
        value = self.rows[len(self.calls)-1]
        if isinstance(value, BaseException): raise value
        return value, {'content-type':'application/xml'}, url

class AcquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import acquire
        cls.m = acquire
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
    def resolve(self, source, rows, identity=DOI, version=None):
        f = Fixtures(rows)
        return self.m.resolve(source, identity, version, f), f
    def test_crossref_metadata_not_fulltext(self):
        result,f = self.resolve('crossref',[{'message':{'DOI':DOI,'title':['Fixture'],'abstract':'Abstract only','type':'journal-article','link':[{'URL':'https://publisher.example/paper.pdf','content-type':'application/pdf','content-version':'vor'}]}}])
        self.assertEqual(result['state'],'metadata'); self.assertEqual(result['reading_depth'],'metadata')
        self.assertEqual(result['materials'][0]['state'],'candidate_url'); self.assertEqual(result['materials'][0]['kind'],'pdf')
        self.assertEqual(result['license'],None); self.assertNotIn('mailto',f.calls[0])
    def test_crossref_wrong_doi_rejected(self):
        with self.assertRaises(self.m.AcquisitionError): self.resolve('crossref',[{'message':{'DOI':'10.9999/other'}}])
    def test_datacite_landing_is_not_pdf(self):
        r,f=self.resolve('datacite',[{'data':{'attributes':{'doi':DOI,'titles':[{'title':'Data'}],'url':'https://repo.example/item','types':{'resourceTypeGeneral':'Dataset'}}}}])
        self.assertEqual(r['materials'][0]['kind'],'landing');self.assertEqual(r['publication_status'],'unknown')
    def test_openalex_locations_dedup_and_gate(self):
        loc={'pdf_url':'https://repo.example/a.pdf','landing_page_url':'https://repo.example/a','version':'acceptedVersion','is_oa':True,'license':None}
        r,f=self.resolve('openalex',[{'doi':'https://doi.org/'+DOI,'title':'Fixture','locations':[loc,loc],'best_oa_location':loc}])
        self.assertEqual(len(r['materials']),2);self.assertEqual(r['materials'][0]['version'],'acceptedVersion')
        blocked,_=self.resolve('openalex',[self.m.HTTPFailure(401)])
        self.assertEqual(blocked['state'],'needs_configuration');self.assertEqual(blocked['materials'],[])
    def test_europepmc_mapping_oa_and_unknown_version(self):
        r,f=self.resolve('europepmc',[{'resultList':{'result':[{'doi':DOI,'id':'123','source':'MED','pmcid':'PMC123','title':'X','isOpenAccess':'Y'}]}}])
        self.assertIn('/PMC123/fullTextXML',r['materials'][0]['url']);self.assertEqual(r['version'],'unknown')
        self.assertEqual(r['publication_status'],'unknown');self.assertEqual(r['is_retracted'],None)
    def test_europepmc_wrong_mapping_and_closed(self):
        r,_=self.resolve('europepmc',[{'resultList':{'result':[{'doi':'10.7777/wrong','pmcid':'PMC1','isOpenAccess':'Y'}]}}])
        self.assertEqual(r['state'],'not_found')
        r,_=self.resolve('europepmc',[{'resultList':{'result':[{'doi':DOI,'pmcid':'PMC1','isOpenAccess':'N'}]}}])
        self.assertEqual(r['materials'],[])
    def test_europepmc_pmcid_uses_official_field_and_matches_returned_identity(self):
        r,f=self.resolve('europepmc',[{'resultList':{'result':[{'id':'99','source':'MED','pmcid':'PMC123','isOpenAccess':'Y'}]}}],identity='PMC123')
        self.assertIn('query=PMCID%3APMC123',f.calls[0]);self.assertEqual(r['pmcid'],'PMC123')
    def test_zenodo_identity_files_checksums(self):
        r,f=self.resolve('zenodo',[{'id':123,'conceptrecid':'120','metadata':{'title':'Fixture','doi':'10.5281/zenodo.123','license':{'id':'cc-by-4.0'}},'files':[{'key':'../a.pdf','checksum':'md5:'+hashlib.md5(PDF).hexdigest(),'links':{'self':'https://zenodo.org/api/files/uuid/a.pdf'}}]}],identity='123')
        self.assertEqual(r['version'],'record:123'); self.assertEqual(r['materials'][0]['checksum'],'md5:'+hashlib.md5(PDF).hexdigest())
        self.assertEqual(r['materials'][0]['kind'],'pdf'); self.assertEqual(r['related_identity'],'zenodo-concept:120')
    def test_zenodo_mismatched_id(self):
        with self.assertRaises(self.m.AcquisitionError):self.resolve('zenodo',[{'id':999}],identity='123')
    def test_hal_explicit_file_candidate(self):
        r,f=self.resolve('hal',[{'response':{'docs':[{'doiId_s':DOI,'halId_s':'hal-123','title_s':['Fixture'],'fileMain_s':'https://hal.science/hal-123/document','version_i':2,'openAccess_bool':True}]}}])
        self.assertEqual(r['materials'][0]['kind'],'pdf');self.assertEqual(r['version'],'hal:2')
        self.assertIn('fileMain_s',f.calls[0])
    def test_preprint_version_must_be_chosen_not_latest(self):
        rows={'collection':[{'doi':DOI,'version':'1','title':'X','type':'new results','license':'cc_by','jatsxml':'https://biorxiv.org/x1.xml'},{'doi':DOI,'version':'2','title':'X','type':'withdrawn','jatsxml':'https://biorxiv.org/x2.xml'}]}
        r,_=self.resolve('biorxiv',[rows]);self.assertEqual(r['state'],'needs_version');self.assertEqual(r['versions'],['1','2'])
        r,_=self.resolve('biorxiv',[rows],version='2');self.assertEqual(r['publication_status'],'unknown');self.assertEqual(r['is_withdrawn'],True);self.assertIsNone(r['is_retracted'])
        self.assertIn('x2.xml',r['materials'][0]['url'])
        r,_=self.resolve('medrxiv',[rows],version='3');self.assertEqual(r['state'],'not_found')
    def test_pmc_dataset_discovers_versions_and_requires_selection(self):
        listing=b'<ListBucketResult><IsTruncated>false</IsTruncated><CommonPrefixes><Prefix>PMC123.2/</Prefix></CommonPrefixes><CommonPrefixes><Prefix>PMC123.1/</Prefix></CommonPrefixes></ListBucketResult>'
        r,_=self.resolve('pmc-dataset',[listing],identity='PMC123');self.assertEqual(r['state'],'needs_version');self.assertEqual(set(r['versions']),{'1','2'})
        meta={'pmcid':'PMC123','version':1,'license_code':'TDM','is_manuscript':True,'xml_url':'https://pmc-oa-opendata.s3.amazonaws.com/PMC123.1/PMC123.1.xml?md5='+hashlib.md5(XML).hexdigest()}
        r,_=self.resolve('pmc-dataset',[listing,meta],identity='PMC123',version='1');self.assertEqual(r['is_retracted'],None);self.assertEqual(r['license'],'TDM');self.assertEqual(r['materials'][0]['checksum'],'md5:'+hashlib.md5(XML).hexdigest())
    def test_pmc_pagination_refuses_silent_incomplete_list(self):
        with self.assertRaises(self.m.AcquisitionError):self.resolve('pmc-dataset',[b'<ListBucketResult><IsTruncated>true</IsTruncated></ListBucketResult>'],identity='PMC123')
    def test_pmc_s3_links_translate_only_known_bucket(self):
        listing=b'<ListBucketResult><IsTruncated>false</IsTruncated><CommonPrefixes><Prefix>PMC123.1/</Prefix></CommonPrefixes></ListBucketResult>'
        meta={'pmcid':'PMC123','version':1,'xml_url':'s3://pmc-oa-opendata/PMC123.1/PMC123.1.xml?md5='+hashlib.md5(XML).hexdigest()}
        r,_=self.resolve('pmc-dataset',[listing,meta],identity='PMC123',version='1')
        self.assertTrue(r['materials'][0]['url'].startswith('https://pmc-oa-opendata.s3.amazonaws.com/PMC123.1/'))
        meta['xml_url']='s3://other-bucket/PMC123.1/PMC123.1.xml?md5='+hashlib.md5(XML).hexdigest()
        with self.assertRaises(self.m.AcquisitionError):self.resolve('pmc-dataset',[listing,meta],identity='PMC123',version='1')
    def test_sensitive_configuration_missing_no_requests(self):
        for src in ('unpaywall','openalex-content','core'):
            r,f=self.resolve(src,[]);self.assertEqual(r['state'],'needs_configuration');self.assertEqual(f.calls,[])
    def test_import_requires_provenance_and_no_secrets(self):
        for obj in ({'title':'X'}, {'provider':'scispace','origin_url':'https://example.org','identity':DOI,'api_key':'secret'}):
            with self.assertRaises(self.m.AcquisitionError):self.m.import_result(obj)
    def test_plugin_passages_do_not_become_fulltext(self):
        r=self.m.import_result({'provider':'scispace','origin_url':'https://example.org/search','identity':DOI,'title':'Fixture','material_kind':'passages','content':'Excerpt','fulltext_url':'/paper.pdf','fulltext_saved':True})
        self.assertEqual(r['state'],'passages');self.assertEqual(r['reading_depth'],'metadata');self.assertEqual(r['materials'][0]['url'],'https://example.org/paper.pdf');self.assertEqual(r['materials'][0]['state'],'candidate_url')
    def test_scholar_normalizes_bare_doi_for_host(self):
        self.assertEqual(self.m.scholar_identifier('10.1038/s41586-021-03819-2'),'https://doi.org/10.1038/s41586-021-03819-2')
        self.assertEqual(self.m.scholar_identifier('https://doi.org/10.1038/s41586-021-03819-2'),'https://doi.org/10.1038/s41586-021-03819-2')
    def test_registration_draft_does_not_claim_read_or_verified(self):
        c=self.candidate();p=self.m.save(c,self.root/'related_work',0,client=Fixtures([XML]))
        draft=self.m.registration_draft(p,self.root,'work-example','source-example','paper-example')
        self.assertEqual(draft['paper']['reading_depth'],'metadata');self.assertEqual(draft['paper']['review_status'],'needs_review')
        self.assertEqual(draft['source']['material_binding']['sha256'],hashlib.sha256(XML).hexdigest())
        self.assertEqual(draft['paper']['source_id'],'source-example');self.assertEqual(draft['source']['schema_version'],2)
    def test_remote_sensitive_text_never_emitted(self):
        with self.assertRaises(self.m.AcquisitionError):self.resolve('crossref',[{'message':{'DOI':DOI,'title':['error api_key=private-service-key']}}])
    def test_nested_sensitive_error_payload_refused(self):
        with self.assertRaises(self.m.AcquisitionError):self.m.import_result({'provider':'fixture','origin_url':'https://example.org','identity':DOI,'content':'remote error https://service.example/?access_token=secret','material_kind':'passages'})
    def test_url_validation(self):
        for url in ('file:///tmp/a','http://example.org/a','https://user:pass@example.org','https://127.0.0.1/a','https://[::1]/','https://169.254.169.254/','https://example.org?api_key=secret','https://example.org?X-Amz-Signature=secret','https://example.org/%0d%0aX','https://example.org:8443/'):
            with self.subTest(url=url),self.assertRaises(self.m.AcquisitionError):self.m.safe_url(url)
    def test_xml_body_jats_tei_no_entity_no_abstract_upgrade(self):
        self.assertEqual(self.m.verify_material(XML,'xml','application/xml'),'jats')
        tei=b'<TEI><teiHeader/><text><body><p>'+b'evidence '*40+b'</p></body></text></TEI>'
        self.assertEqual(self.m.verify_material(tei,'xml','text/xml'),'tei')
        for body in (b'<article><front><abstract>'+b'A'*500+b'</abstract></front></article>',b'<!DOCTYPE x [<!ENTITY e "boom">]><article/>',b'<html><body>Login</body></html>'):
            with self.assertRaises(self.m.AcquisitionError):self.m.verify_material(body,'xml','application/xml')
    def test_pdf_and_html_structure(self):
        self.assertEqual(self.m.verify_material(PDF,'pdf','application/pdf'),'pdf')
        for body,ctype in ((b'<html>404</html>','text/html'),(b'%PDF-1.4\n%%EOF','application/pdf'),(PDF,'text/html')):
            with self.assertRaises(self.m.AcquisitionError):self.m.verify_material(body,'pdf',ctype)
        html=('<html><article><h1>Paper</h1><h2>Methods</h2><p>'+('research '*120)+'</p><h2>Results</h2><p>'+('finding '*120)+'</p></article></html>').encode()
        self.assertEqual(self.m.verify_material(html,'html','text/html'),'html')
        with self.assertRaises(self.m.AcquisitionError):self.m.verify_material(b'<html><article><h1>Abstract</h1>'+b'x '*1000+b'</article></html>','html','text/html')
    def candidate(self):
        return self.m.import_result({'provider':'fixture','origin_url':'https://example.org/search','identity':DOI,'version':'v1','title':'Fixture','material_kind':'metadata','materials':[{'kind':'xml','url':'https://example.org/a.xml','version':'v1','checksum':'md5:'+hashlib.md5(XML).hexdigest()}]})
    def test_atomic_save_repeat_and_new_snapshot(self):
        c=self.candidate();f=Fixtures([XML]);p=self.m.save(c,self.root,0,client=f)
        manifest=json.loads((p/'manifest.json').read_text());self.assertEqual(manifest['state'],'fulltext_saved');self.assertEqual(manifest['reading_depth'],'metadata');self.assertEqual(manifest['identity_verified'],False)
        before=(p/'material.xml').read_bytes();self.assertEqual(before,XML)
        self.assertEqual(self.m.save(c,self.root,0,client=Fixtures([XML])),p)
        c['materials'][0].pop('checksum');new=XML.replace(b'Fixture',b'Changed');p2=self.m.save(c,self.root,0,client=Fixtures([new]));self.assertNotEqual(p,p2);self.assertEqual((p/'material.xml').read_bytes(),before)
    def test_failure_hash_wrong_type_and_interrupt_preserve_old(self):
        c=self.candidate();p=self.m.save(c,self.root,0,client=Fixtures([XML]));before={str(x):x.read_bytes() for x in p.iterdir()}
        for body in (b'<html>blocked</html>',XML+b'bad',KeyboardInterrupt()):
            with self.subTest(body=type(body).__name__),self.assertRaises((self.m.AcquisitionError,KeyboardInterrupt)):self.m.save(c,self.root,0,client=Fixtures([body]))
            self.assertEqual({str(x):x.read_bytes() for x in p.iterdir()},before)
        self.assertFalse(list(self.root.rglob('.stage-*')))
    def test_local_import_symlink_and_no_auto_source_execution(self):
        c=self.candidate();f=self.root/'input.xml';f.write_bytes(XML);p=self.m.save(c,self.root/'out',0,local_file=f);self.assertTrue((p/'manifest.json').exists())
        link=self.root/'link.xml';link.symlink_to(f)
        with self.assertRaises(self.m.AcquisitionError):self.m.save(c,self.root/'out',0,local_file=link)
        c['materials'][0]['kind']='source'
        with self.assertRaises(self.m.AcquisitionError):self.m.save(c,self.root/'out',0,local_file=f)
    def test_destination_symlink_and_cache_tamper_refused(self):
        c=self.candidate();p=self.m.save(c,self.root,0,client=Fixtures([XML]));(p/'material.xml').write_bytes(b'tampered')
        with self.assertRaises(self.m.AcquisitionError):self.m.save(c,self.root,0,client=Fixtures([XML]))
        link=self.root/'out';link.symlink_to(self.root/'outside',target_is_directory=True)
        with self.assertRaises(self.m.AcquisitionError):self.m.save(c,link,0,client=Fixtures([XML]))

class NetworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import acquire
        cls.m=acquire
    def public(self,host,port,**kwargs):return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))]
    def test_dns_all_addresses_public_and_pin(self):
        bad=lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))]
        with self.assertRaises(self.m.AcquisitionError):self.m.SafeHTTP(resolver=bad).get('https://example.org')
        class Conn:
            def __init__(self,host,address,timeout):self.host=host;self.address=address
            def request(self,*a,**k):pass
            def getresponse(self):return Reply(200,b'{}',{'content-type':'application/json'})
            def close(self):pass
        c=self.m.SafeHTTP(resolver=self.public,connection_factory=Conn,pause=lambda _:None)
        self.assertEqual(c.json('https://example.org'),{})
    def test_redirect_revalidates_and_denies_private(self):
        m=self.m
        class Conn:
            def __init__(self,*a,**k):pass
            def request(self,*a,**k):pass
            def getresponse(self):return Reply(302,b'',{'location':'https://127.0.0.1/secret'})
            def close(self):pass
        with self.assertRaises(m.AcquisitionError):m.SafeHTTP(resolver=self.public,connection_factory=Conn,pause=lambda _:None).get('https://example.org')
    def test_limits_retry_auth_and_length(self):
        m=self.m
        def run(replies,limit=1024):
            events=[]
            class Conn:
                def __init__(self,*a,**k):events.append('connect')
                def request(self,*a,**k):pass
                def getresponse(self):return replies.pop(0)
                def close(self):pass
            c=m.SafeHTTP(resolver=self.public,connection_factory=Conn,pause=lambda _:None)
            return c,events,lambda:c.get('https://example.org',limit=limit)
        c,events,fn=run([Reply(503),Reply(200,b'ok')]);self.assertEqual(fn()[0],b'ok');self.assertEqual(len(events),2)
        c,events,fn=run([Reply(403)]);
        with self.assertRaises(m.HTTPFailure):fn()
        self.assertEqual(len(events),1)
        for r in (Reply(200,b'abcdef'),Reply(200,b'abc',{'content-length':'9'}),Reply(200,b'abc',{'content-encoding':'gzip'})):
            c,events,fn=run([r],limit=4)
            with self.assertRaises(m.AcquisitionError):fn()
    def test_request_cap_and_redirect_loop(self):
        class Conn:
            def __init__(self,*a,**k):pass
            def request(self,*a,**k):pass
            def getresponse(self):return Reply(302,b'',{'location':'https://example.org/next'})
            def close(self):pass
        c=self.m.SafeHTTP(resolver=self.public,connection_factory=Conn,pause=lambda _:None)
        with self.assertRaises(self.m.AcquisitionError):c.get('https://example.org')
        self.assertLessEqual(c.requests,5)
    def test_public_object_json_octet_stream_only_when_json_parses(self):
        class Conn:
            def __init__(self,*a,**k):pass
            def request(self,*a,**k):pass
            def getresponse(self):return Reply(200,b'{"version":1}',{'content-type':'application/octet-stream'})
            def close(self):pass
        c=self.m.SafeHTTP(resolver=self.public,connection_factory=Conn,pause=lambda _:None)
        self.assertEqual(c.json('https://pmc-oa-opendata.s3.amazonaws.com/a.json'),{'version':1})
    def test_body_total_deadline_enforced(self):
        tick=[0]
        class TimedReply(Reply):
            def read(self,*args):tick[0]=46;return super().read(*args)
            def read1(self,*args):return self.read(*args)
        class Conn:
            def __init__(self,*a,**k):pass
            def request(self,*a,**k):pass
            def getresponse(self):return TimedReply(200,b'body')
            def close(self):pass
        c=self.m.SafeHTTP(resolver=self.public,connection_factory=Conn,pause=lambda _:None,clock=lambda:tick[0])
        with self.assertRaises(self.m.AcquisitionError):c.get('https://example.org')
    def test_reader_uses_one_io_read_to_check_deadline_between_chunks(self):
        class OneReadReply(Reply):
            def read(self,*a):raise AssertionError('unbounded multi-read call')
            def read1(self,n):return io.BytesIO.read(self,n)
        class Conn:
            def __init__(self,*a,**k):pass
            def request(self,*a,**k):pass
            def getresponse(self):return OneReadReply(200,b'body')
            def close(self):pass
        c=self.m.SafeHTTP(resolver=self.public,connection_factory=Conn,pause=lambda _:None)
        self.assertEqual(c.get('https://example.org')[0],b'body')
    def test_mixed_dns_answers_refused_before_connect(self):
        called=[]
        def mixed(*a,**k):return self.public(*a,**k)+[(socket.AF_INET,socket.SOCK_STREAM,6,'',('10.0.0.1',443))]
        c=self.m.SafeHTTP(resolver=mixed,connection_factory=lambda *a,**k:called.append(a),pause=lambda _:None)
        with self.assertRaises(self.m.AcquisitionError):c.get('https://example.org')
        self.assertEqual(called,[])
    def test_source_binding_change_invalidates_dependents(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('checker_acquire',ROOT/'scripts/check-research.py');checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp).resolve();research=project/'research';research.mkdir()
            artifact=project/'material.xml';artifact.write_bytes(XML)
            common={'schema_version':2,'rev':1,'updated_at':'2026-10-01T00:00:00Z'}
            source={**common,'id':'s','url':'https://example.org/a','retrieved_at':common['updated_at'],'status':'active','material_binding':{'path':'material.xml','sha256':hashlib.sha256(XML).hexdigest()}}
            paper={**common,'id':'p','source_id':'s','source_rev':1,'work_id':'w','title':'Fixture','version':'unknown','publication_status':'unknown','reading_depth':'metadata','review_status':'current'}
            for kind,rows in [('sources',[source]),('papers',[paper]),('claims',[]),('opportunities',[])]:
                (research/(kind+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in rows))
            errors,*_=checker.validate(research);self.assertEqual(errors,[])
            artifact.write_bytes(b'changed');errors,latest,stale,_,_=checker.validate(research)
            self.assertIn(('papers','p'),stale);self.assertTrue(any('needs_review' in e for e in errors))

class Reply(io.BytesIO):
    def __init__(self,status,body=b'',headers=None):super().__init__(body);self.status=status;self._headers=headers or {}
    def getheaders(self):return list(self._headers.items())

if __name__ == '__main__':unittest.main()
