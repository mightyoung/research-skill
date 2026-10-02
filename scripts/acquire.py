"""Credential-free public metadata resolution and controlled material import.

Locally authored. Uses only Python's standard library; no plugin/client SDK.
Downloaded text is inert evidence, never instructions or executable input.
"""
import datetime as dt
import hashlib
import html.parser
import http.client
import ipaddress
import json
import os
from pathlib import Path
import queue
import re
import socket
import ssl
import tempfile
import threading
import time
import urllib.parse as U
import xml.etree.ElementTree as ET

MAX_BYTES = 32 * 1024 * 1024
MAX_METADATA = 4 * 1024 * 1024
SOURCES = ('crossref', 'datacite', 'openalex', 'europepmc', 'pmc-dataset',
           'zenodo', 'hal', 'biorxiv', 'medrxiv', 'unpaywall', 'openalex-content', 'core')
SECRET = re.compile(r'(?:token|api[-_]?key|authorization|password|passwd|cookie|secret|signature|credential|x-amz-|x-goog-)', re.I)

class AcquisitionError(Exception):
    """Messages must not include raw remote errors, URLs or credential values."""

class HTTPFailure(AcquisitionError):
    def __init__(self, status):
        self.status = status
        super().__init__(f'HTTP {status}; no authentication or access bypass attempted')

def now(): return dt.datetime.now(dt.timezone.utc).isoformat()

def safe_url(value):
    if not isinstance(value, str) or len(value) > 4096:
        raise AcquisitionError('invalid URL')
    decoded = value
    for _ in range(3): decoded = U.unquote(decoded)
    if any(ord(c) < 33 or ord(c) == 127 for c in decoded) or '\\' in decoded:
        raise AcquisitionError('URL control/whitespace/backslash refused')
    try:
        p = U.urlsplit(value)
        if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443) or p.fragment:
            raise ValueError()
        host = p.hostname.encode('idna').decode('ascii').lower() if p.hostname else ''
    except (ValueError, UnicodeError): raise AcquisitionError('HTTPS URL without credentials, fragment or custom port required') from None
    if not host or host.endswith('.') or host.endswith(('.local', '.internal', '.localhost', '.test', '.invalid')):
        raise AcquisitionError('non-public hostname refused')
    try:
        address = ipaddress.ip_address(host)
        if not address.is_global or address.is_multicast: raise AcquisitionError('non-public IP refused')
    except ValueError:
        if '.' not in host or not re.fullmatch(r'[a-z0-9.-]+', host): raise AcquisitionError('invalid hostname')
    if SECRET.search(U.urlsplit(decoded).query):
        raise AcquisitionError('sensitive URL query refused; configure no credentials for this CLI')
    return U.urlunsplit(('https', p.netloc.lower(), p.path or '/', p.query, ''))

def public_addresses(host, resolver, timeout):
    """Bound caller wait on DNS; daemon lookup cannot make HTTP requests."""
    result = queue.Queue(maxsize=1)
    def lookup():
        try: result.put(resolver(host, 443, type=socket.SOCK_STREAM))
        except Exception: result.put(None)
    threading.Thread(target=lookup, daemon=True).start()
    try: rows = result.get(timeout=timeout)
    except queue.Empty: raise AcquisitionError('DNS deadline exceeded') from None
    if not rows: raise AcquisitionError('DNS lookup unavailable')
    addresses = []
    for family, kind, proto, _, sockaddr in rows:
        try: address = ipaddress.ip_address(sockaddr[0])
        except ValueError: raise AcquisitionError('invalid DNS answer') from None
        if not address.is_global or address.is_multicast: raise AcquisitionError('DNS includes non-public address')
        if family not in (socket.AF_INET, socket.AF_INET6): raise AcquisitionError('unsupported DNS address family')
        addresses.append((family, kind, proto, sockaddr))
    return addresses

class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.address = address
    def connect(self):
        family, kind, proto, sockaddr = self.address
        raw = socket.socket(family, kind, proto)
        try:
            raw.settimeout(self.timeout); raw.connect(sockaddr)
            # TLS certificate and SNI use original hostname; no second DNS lookup.
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException: raw.close(); raise

class SafeHTTP:
    def __init__(self, resolver=socket.getaddrinfo, connection_factory=PinnedHTTPS, pause=time.sleep, clock=time.monotonic):
        self.resolver=resolver; self.connection_factory=connection_factory
        self.pause=pause; self.clock=clock; self.requests=0; self.last={}
    def get(self, url, limit=MAX_BYTES):
        if type(limit) != int or not 0 < limit <= MAX_BYTES: raise AcquisitionError('invalid size limit')
        deadline=self.clock()+45; redirects=0; attempts=0
        while True:
            url=safe_url(url); p=U.urlsplit(url); host=p.hostname
            left=deadline-self.clock()
            if left <= 0: raise AcquisitionError('total request deadline exceeded')
            if self.requests >= 24: raise AcquisitionError('request budget exhausted')
            addresses=public_addresses(host,self.resolver,min(10,left))
            wait=max(0,1-(self.clock()-self.last.get(host,-100)))
            if wait >= deadline-self.clock(): raise AcquisitionError('rate wait exceeds deadline')
            self.pause(wait)
            self.requests+=1;self.last[host]=self.clock();attempts+=1
            conn=self.connection_factory(host,addresses[(attempts-1)%len(addresses)],timeout=min(15,max(.01,deadline-self.clock())))
            sockets=[]
            def interrupt_request(conn=conn,sockets=sockets):
                for sock in [getattr(conn,'sock',None),*sockets]:
                    if sock is not None:
                        try:sock.shutdown(socket.SHUT_RDWR)
                        except OSError:pass
            timer=threading.Timer(max(.01,deadline-self.clock()),interrupt_request);timer.daemon=True;timer.start()
            try:
                conn.request('GET',U.urlunsplit(('', '', p.path or '/', p.query, '')),
                             headers={'User-Agent':'research-workflow-local/3 (public read-only)', 'Accept-Encoding':'identity'})
                if getattr(conn,'sock',None):sockets.append(conn.sock)
                response=conn.getresponse(); headers={k.lower():v for k,v in response.getheaders()}
                if response.status in (301,302,303,307,308):
                    if redirects>=4 or 'location' not in headers: raise AcquisitionError('redirect limit or missing target')
                    url=safe_url(U.urljoin(url,headers['location']));redirects+=1;attempts=0;continue
                if response.status in (408,429,500,502,503,504) and attempts<3:
                    wait=min(2**attempts,4)
                    if wait >= deadline-self.clock():raise AcquisitionError('retry exceeds deadline')
                    self.pause(wait);continue
                if response.status != 200:raise HTTPFailure(response.status)
                if headers.get('content-encoding','identity').lower() != 'identity':raise AcquisitionError('compressed HTTP body refused')
                length=headers.get('content-length')
                if length is not None:
                    if not re.fullmatch(r'\d+',length) or int(length)>limit:raise AcquisitionError('invalid or excessive response length')
                chunks=[];size=0
                while True:
                    left=deadline-self.clock()
                    if left<=0:raise AcquisitionError('body deadline exceeded')
                    if getattr(conn,'sock',None):conn.sock.settimeout(min(15,left))
                    reader=getattr(response,'read1',response.read)
                    chunk=reader(min(65536,limit+1-size))
                    if not chunk:break
                    chunks.append(chunk);size+=len(chunk)
                    if size>limit:raise AcquisitionError('body size limit exceeded')
                if length is not None and size!=int(length):raise AcquisitionError('truncated response')
                if self.clock()>deadline:raise AcquisitionError('total request deadline exceeded')
                return b''.join(chunks),headers,url
            except (OSError,http.client.HTTPException):
                if attempts>=3:raise AcquisitionError('network/TLS request failed; remote error text suppressed') from None
                if deadline-self.clock()<=2:raise AcquisitionError('network retry deadline exceeded') from None
                self.pause(1)
            finally:timer.cancel();conn.close()
    def json(self,url):
        body,headers,final=self.get(url,MAX_METADATA)
        ctype=headers.get('content-type','').lower().split(';')[0]
        # PMC public JSON objects use binary/octet-stream. Permit that only
        # on the documented bucket and .json object path, still parse JSON.
        object_json=U.urlsplit(final).hostname=='pmc-oa-opendata.s3.amazonaws.com' and U.urlsplit(final).path.endswith('.json') and ctype in ('application/octet-stream','binary/octet-stream')
        if 'json' not in ctype and not object_json:raise AcquisitionError('metadata response is not JSON')
        try: value=json.loads(body)
        except (ValueError,UnicodeError):raise AcquisitionError('invalid metadata JSON') from None
        if not isinstance(value,dict):raise AcquisitionError('metadata JSON must be object')
        return value

def doi(value):
    if not isinstance(value,str):raise AcquisitionError('DOI required')
    value=re.sub(r'^(?:https://(?:dx\.)?doi.org/|doi:\s*)','',value.strip(),flags=re.I).lower()
    if not re.fullmatch(r'10\.\d{4,9}/[^\s?#]+',value):raise AcquisitionError('invalid DOI')
    return value

def scholar_identifier(value):
    """For host Scholar tools: bare DOI is not reliably accepted."""
    return 'https://doi.org/'+doi(value)

def secret_free(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if SECRET.search(str(key)):raise AcquisitionError('sensitive key refused; do not persist plugin errors or authentication payloads')
            secret_free(item)
    elif isinstance(value,list):
        for item in value:secret_free(item)
    elif isinstance(value,str):
        if re.search(r'(?:Bearer\s+\S+|(?:api[_-]?key|access[_-]?token|password|secret|x-amz-signature)\s*[=:]\s*\S+|[?&](?:token|signature|cookie|credential)=)',value,re.I):
            raise AcquisitionError('sensitive payload refused; discard remote error text')

def base(source,identity,origin):
    return {'acquisition_schema':1,'provider':source,'identity':identity,'origin_url':safe_url(origin),
            'retrieved_at':now(),'title':'Unknown title','version':'unknown','publication_status':'unknown',
            'is_retracted':None,'is_manuscript':None,'license':None,'state':'metadata',
            'reading_depth':'metadata','materials':[], 'notes':[]}

def material(record,url,kind,version=None,license=None,checksum=None):
    if not url:return
    try:url=safe_url(U.urljoin(record['origin_url'],url))
    except AcquisitionError:
        record['notes'].append('An unsafe candidate URL was omitted; raw URL not persisted.');return
    if any(x['url']==url and x['kind']==kind for x in record['materials']):return
    item={'url':url,'kind':kind,'version':str(version or record['version']),
          'license':license,'state':'candidate_url'}
    if checksum:item['checksum']=checksum
    record['materials'].append(item)

def same_doi(value,expected):
    try:return doi(value)==expected
    except AcquisitionError:return False

def first_title(value):
    if isinstance(value,list):value=value[0] if value else None
    return value if isinstance(value,str) and value.strip() else 'Unknown title'

def resolve(source,identity,version=None,client=None):
    if source not in SOURCES:raise AcquisitionError('unsupported source')
    client=client or SafeHTTP()
    if source in ('unpaywall','openalex-content','core'):
        r=base(source,doi(identity),'https://doi.org/'+doi(identity));r.update(state='needs_configuration')
        r['notes']=['Not called. Unpaywall requires an explicitly authorized email; hosted OpenAlex content requires a key; CORE adapter is deferred. This CLI does not accept credentials.'];return r
    try:
        result=_resolve(source,identity,version,client)
        secret_free(result)
        return result
    except HTTPFailure as error:
        r=base(source,str(identity),'https://doi.org/'+doi(identity) if source not in ('zenodo','pmc-dataset') else ('https://zenodo.org/' if source=='zenodo' else 'https://pmc-oa-opendata.s3.amazonaws.com/'))
        r['state']='needs_configuration' if error.status==401 else ('not_found' if error.status in (404,410) else 'blocked')
        r['http_status']=error.status;r['notes']=['Public request stopped; no retry with credentials or access bypass.'];return r

def _resolve(source,identity,version,client):
    if source in ('zenodo','pmc-dataset'):
        return _zenodo(identity,client) if source=='zenodo' else _pmc(identity,version,client)
    if source=='europepmc' and re.fullmatch(r'(?:PMID:)?\d+|PMC\d+',str(identity),re.I):
        token=str(identity).upper();query=('EXT_ID:'+token.removeprefix('PMID:')+' AND SRC:MED') if not token.startswith('PMC') else 'PMCID:'+token
        expected=None
    else:expected=doi(identity);query='DOI:'+expected;identity=expected
    encoded=U.quote(str(identity),safe='')
    if source=='crossref':
        url='https://api.crossref.org/works/'+encoded;r=base(source,identity,url);v=client.json(url).get('message',{})
        if not same_doi(v.get('DOI'),identity):raise AcquisitionError('Crossref identity mismatch')
        r['title']=first_title(v.get('title'));r['raw_type']=v.get('type');r['abstract']=v.get('abstract')
        r['publication_status']='preprint' if v.get('type')=='posted-content' else 'unknown'
        for link in v.get('link',[]):
            kind={'application/pdf':'pdf','application/xml':'xml','text/xml':'xml','text/html':'html'}.get(link.get('content-type'),'landing')
            material(r,link.get('URL'),kind,link.get('content-version'))
        r['license']=v.get('license') or None;r['updates']=v.get('update-to') or [];return r
    if source=='datacite':
        url='https://api.datacite.org/dois/'+encoded;r=base(source,identity,url);v=client.json(url).get('data',{}).get('attributes',{})
        if not same_doi(v.get('doi'),identity):raise AcquisitionError('DataCite identity mismatch')
        r['title']=first_title([x.get('title') for x in v.get('titles',[])]);r['license']=v.get('rightsList') or None
        r['version']=str(v.get('version') or 'unknown');r['raw_type']=v.get('types');material(r,v.get('url'),'landing');return r
    if source=='openalex':
        url='https://api.openalex.org/works/'+U.quote('https://doi.org/'+identity,safe=':/');r=base(source,identity,url);v=client.json(url)
        if not same_doi(v.get('doi'),identity):raise AcquisitionError('OpenAlex identity mismatch')
        r['title']=first_title(v.get('title') or v.get('display_name'));r['provider_id']=v.get('id')
        r['is_retracted']=v.get('is_retracted') if type(v.get('is_retracted'))==bool else None
        if r['is_retracted'] is True:r['publication_status']='retracted'
        for loc in [*(v.get('locations') or []),v.get('best_oa_location') or {}]:
            if loc.get('is_oa') is not True:continue
            material(r,loc.get('pdf_url'),'pdf',loc.get('version'),loc.get('license'))
            material(r,loc.get('landing_page_url'),'landing',loc.get('version'),loc.get('license'))
        return r
    if source=='europepmc':
        url='https://www.ebi.ac.uk/europepmc/webservices/rest/search?'+U.urlencode({'query':query,'format':'json','resultType':'core','pageSize':10})
        r=base(source,str(identity),url);rows=client.json(url).get('resultList',{}).get('result',[])
        rows=[x for x in rows if same_doi(x.get('doi'),expected)] if expected else [x for x in rows if str(x.get('id'))==str(identity).upper().removeprefix('PMID:') or x.get('pmcid')==str(identity).upper()]
        if not rows:r['state']='not_found';return r
        if len({x.get('pmcid') for x in rows if x.get('pmcid')})>1:raise AcquisitionError('ambiguous Europe PMC identity; choose PMCID')
        v=rows[0];r['title']=first_title(v.get('title'));r['pmcid']=v.get('pmcid');r['pmid']=v.get('id');r['abstract']=v.get('abstractText');r['license']=v.get('license')
        r['notes'].append('Europe PMC endpoint provides a retrieved snapshot, not a fixed historical PMC article version; use pmc-dataset for explicit versions.')
        if v.get('pmcid') and re.fullmatch(r'PMC\d+',v['pmcid']) and v.get('isOpenAccess')=='Y':
            material(r,'https://www.ebi.ac.uk/europepmc/webservices/rest/'+v['pmcid']+'/fullTextXML','xml')
        return r
    if source=='hal':
        url='https://api.archives-ouvertes.fr/search/?'+U.urlencode({'q':'doiId_s:"'+identity+'"','fl':'doiId_s,halId_s,title_s,version_i,fileMain_s,files_s,uri_s,licence_s,openAccess_bool','wt':'json','rows':10})
        r=base(source,identity,url);rows=client.json(url).get('response',{}).get('docs',[])
        rows=[x for x in rows if any(same_doi(d,identity) for d in (x.get('doiId_s') if isinstance(x.get('doiId_s'),list) else [x.get('doiId_s')]))]
        if version is not None:rows=[x for x in rows if str(x.get('version_i'))==str(version)]
        if not rows:r['state']='not_found';return r
        if len(rows)>1:r.update(state='needs_version',versions=[str(x.get('version_i','unknown')) for x in rows]);return r
        v=rows[0];r['title']=first_title(v.get('title_s'));r['version']='hal:'+str(v['version_i']) if v.get('version_i') else 'unknown';r['provider_id']=v.get('halId_s');r['license']=v.get('licence_s')
        material(r,v.get('uri_s'),'landing')
        if v.get('openAccess_bool') is True:material(r,v.get('fileMain_s'),'pdf',r['version'],r['license'])
        return r
    if source in ('biorxiv','medrxiv'):
        url='https://api.biorxiv.org/details/'+source+'/'+U.quote(identity,safe='/')+'/na/json';r=base(source,identity,url)
        rows=[x for x in client.json(url).get('collection',[]) if same_doi(x.get('doi'),identity)]
        if version is None:
            r.update(state='needs_version' if rows else 'not_found',versions=list(dict.fromkeys(str(x.get('version')) for x in rows)));return r
        rows=[x for x in rows if str(x.get('version'))==str(version).removeprefix('v')]
        if len(rows)!=1:r['state']='not_found' if not rows else 'ambiguous';return r
        v=rows[0];r.update(title=first_title(v.get('title')),version='v'+str(v['version']),license=v.get('license'),publication_status='preprint',raw_status=v.get('type'))
        if 'withdraw' in str(v.get('type','')).lower():
            r.update(publication_status='unknown',is_withdrawn=True)
            r['notes'].append('Withdrawn preprint; requires review. Withdrawal is not automatically a formal retraction.')
        r['published_doi']=v.get('published') or None
        material(r,v.get('jatsxml'),'xml',r['version'],r['license'])
        r['notes'].append('Only links explicitly supplied for the selected version are candidates; no guessed PDF path.');return r
    raise AcquisitionError('adapter unavailable')

def xml_tree(body):
    if len(body)>MAX_BYTES:raise AcquisitionError('XML size exceeded')
    # External DOCTYPE is common in JATS. ElementTree never fetches it;
    # internal DTD subsets/entities and UTF-16 (byte-filter bypass) are refused.
    if b'\x00' in body or re.search(br'<!ENTITY|<!DOCTYPE[^>]*\[',body,re.I):raise AcquisitionError('XML internal DTD/entities refused')
    try:return ET.fromstring(body)
    except ET.ParseError:raise AcquisitionError('invalid XML') from None

def _pmc(identity,version,client):
    identity=str(identity).upper()
    if not re.fullmatch(r'PMC[1-9]\d*',identity):raise AcquisitionError('PMCID required')
    url='https://pmc-oa-opendata.s3.amazonaws.com/?'+U.urlencode({'list-type':2,'prefix':identity+'.','delimiter':'/'})
    r=base('pmc-dataset',identity,url);body,_,_=client.get(url,MAX_METADATA);tree=xml_tree(body)
    def tag(node):return node.tag.rsplit('}',1)[-1]
    if any(tag(x)=='IsTruncated' and x.text!='false' for x in tree.iter()):raise AcquisitionError('PMC version listing incomplete; refuse automatic version choice')
    versions=[]
    for node in tree.iter():
        if tag(node)=='CommonPrefixes':
            for child in node:
                match=re.fullmatch(re.escape(identity)+r'\.([1-9]\d*)/?',child.text or '') if tag(child)=='Prefix' else None
                if match:versions.append(match[1])
    r['versions']=list(dict.fromkeys(versions))
    if version is None:r['state']='needs_version' if versions else 'not_found';return r
    if str(version) not in versions:r['state']='not_found';return r
    key=identity+'.'+str(version);metadata='https://pmc-oa-opendata.s3.amazonaws.com/'+key+'/'+key+'.json';v=client.json(metadata)
    if str(v.get('pmcid')).upper()!=identity or str(v.get('version'))!=str(version):raise AcquisitionError('PMC metadata identity/version mismatch')
    r.update(origin_url=metadata,title=first_title(v.get('title')),version=key,license=v.get('license_code'),
             is_retracted=v.get('is_retracted') if type(v.get('is_retracted'))==bool else None,
             is_manuscript=v.get('is_manuscript') if type(v.get('is_manuscript'))==bool else None)
    if r['is_retracted'] is True:r['publication_status']='retracted'
    for field,kind in [('xml_url','xml'),('pdf_url','pdf'),('text_url','text')]:
        link=v.get(field)
        if not link:continue
        if link.startswith('s3://'):
            s3=U.urlsplit(link)
            if s3.netloc!='pmc-oa-opendata' or s3.fragment:raise AcquisitionError('PMC S3 link uses unexpected bucket or fragment')
            link=U.urlunsplit(('https','pmc-oa-opendata.s3.amazonaws.com',s3.path,s3.query,''))
        parsed=U.urlsplit(safe_url(link))
        if parsed.hostname!='pmc-oa-opendata.s3.amazonaws.com' or not parsed.path.startswith('/'+key+'/'):raise AcquisitionError('PMC material points outside selected version')
        md5=U.parse_qs(parsed.query).get('md5',[''])[0]
        if not re.fullmatch(r'[0-9a-fA-F]{32}',md5):raise AcquisitionError('PMC material missing valid MD5')
        material(r,link,kind,key,r['license'],'md5:'+md5.lower())
    r['notes'].append('NLM is the source; no NIH/NLM endorsement. PMC version numbers are not a quality ranking. TDM is not a redistribution grant.');return r

def _zenodo(identity,client):
    identity=str(identity)
    if not re.fullmatch(r'[1-9]\d*',identity):raise AcquisitionError('explicit Zenodo record ID required')
    url='https://zenodo.org/api/records/'+identity;r=base('zenodo','zenodo:'+identity,url);v=client.json(url)
    if str(v.get('id'))!=identity:raise AcquisitionError('Zenodo record identity mismatch; concept/latest redirect not accepted; select an explicit version record')
    m=v.get('metadata') or {};r.update(title=first_title(m.get('title')),version='record:'+identity,license=m.get('license'),doi=m.get('doi'))
    r['related_identity']='zenodo-concept:'+str(v['conceptrecid']) if v.get('conceptrecid') else None
    for file in v.get('files',[]):
        name=str(file.get('key') or '');kind='pdf' if name.lower().endswith('.pdf') else ('xml' if name.lower().endswith('.xml') else 'other')
        link=(file.get('links') or {}).get('content') or (file.get('links') or {}).get('self')
        material(r,link,kind,r['version'],r['license'],file.get('checksum'))
    return r

def import_result(value):
    """Whitelisted host envelope, never the raw MCP response/error/account."""
    if not isinstance(value,dict):raise AcquisitionError('import envelope must be object')
    secret_free(value)
    if any(not isinstance(value.get(k),str) or not value[k].strip() for k in ('provider','origin_url','identity')):
        raise AcquisitionError('provider, origin_url and identity required')
    r=base(value['provider'],value['identity'],value['origin_url']);r['title']=first_title(value.get('title'));r['version']=str(value.get('version') or 'unknown')
    kind=value.get('material_kind','metadata')
    if kind not in ('metadata','abstract','passages'):raise AcquisitionError('host envelope supports metadata/abstract/passages; import actual fulltext file separately')
    r['state']=kind
    if kind in ('abstract','passages'):
        if not isinstance(value.get('content'),str):raise AcquisitionError('abstract/passages content required')
        r[kind]=value['content']
    for key in ('license','publication_status','is_retracted','is_manuscript'):
        if key in value:r[key]=value[key]
    r['notes'].append('Host result is untrusted evidence. Provider claim fulltext_saved is ignored; reading depth is not upgraded.')
    for item in value.get('materials',[]):
        if not isinstance(item,dict) or item.get('kind') not in ('pdf','xml','html','text','landing','source','other'):raise AcquisitionError('invalid material descriptor')
        material(r,item.get('url'),item['kind'],item.get('version'),item.get('license'),item.get('checksum'))
    material(r,value.get('fulltext_url'),'landing')
    return r

class ArticleHTML(html.parser.HTMLParser):
    def __init__(self):super().__init__();self.region=0;self.words=[];self.headings=0;self.password=False;self.ignore=0
    def handle_starttag(self,tag,attrs):
        if tag in ('article','main'):self.region+=1
        if tag in ('script','style'):self.ignore+=1
        if self.region and tag in ('h2','h3'):self.headings+=1
        if tag=='input' and dict(attrs).get('type')=='password':self.password=True
    def handle_endtag(self,tag):
        if tag in ('article','main'):self.region=max(0,self.region-1)
        if tag in ('script','style'):self.ignore=max(0,self.ignore-1)
    def handle_data(self,data):
        if self.region and not self.ignore:self.words.extend(data.split())

def verify_material(body,kind,ctype=''):
    if not body or len(body)>MAX_BYTES:raise AcquisitionError('empty/oversized material')
    ctype=ctype.lower().split(';')[0]
    if kind=='pdf':
        if ctype not in ('application/pdf','application/octet-stream','binary/octet-stream',''):raise AcquisitionError('PDF media type mismatch')
        if not (body.startswith(b'%PDF-') and b'%%EOF' in body[-2048:] and re.search(br'/Type\s*/Page\b',body) and b'startxref' in body[-4096:]):raise AcquisitionError('PDF lacks required document structure; full PDF parsing not performed')
        return 'pdf'
    if kind=='xml':
        if ctype not in ('application/xml','text/xml','application/jats+xml','application/octet-stream','binary/octet-stream',''):raise AcquisitionError('XML media type mismatch')
        tree=xml_tree(body);tag=lambda x:x.tag.rsplit('}',1)[-1];root=tag(tree)
        bodies=[x for x in tree.iter() if tag(x)=='body']
        content=' '.join(' '.join(x.itertext()) for x in bodies)
        if root not in ('article','TEI') or not bodies or len(content.strip())<100:raise AcquisitionError('XML is not JATS/TEI article body; abstract-only material refused')
        if root=='article' and not any(tag(x)=='front' for x in tree):raise AcquisitionError('JATS front metadata missing')
        if root=='TEI' and not any(tag(x)=='teiHeader' for x in tree):raise AcquisitionError('TEI header missing')
        return 'jats' if root=='article' else 'tei'
    if kind=='html':
        if ctype not in ('text/html',''):raise AcquisitionError('HTML media type mismatch')
        try:p=ArticleHTML();p.feed(body.decode('utf-8'))
        except (ValueError,UnicodeError):raise AcquisitionError('invalid UTF-8 HTML') from None
        if p.password or len(p.words)<200 or p.headings<2:raise AcquisitionError('HTML lacks conservative article body evidence; landing/abstract/login page refused')
        return 'html'
    raise AcquisitionError('only PDF, JATS/TEI XML and conservatively verified HTML supported; plain text/source deferred')

def safe_directory(path):
    path=Path(os.path.abspath(path))
    for part in [*reversed(path.parents),path]:
        if part.is_symlink():raise AcquisitionError('symlink destination refused')
        if part.exists() and not part.is_dir():raise AcquisitionError('destination component is not directory')
    path.mkdir(parents=True,exist_ok=True);return path

def save(record,destination,index,client=None,local_file=None):
    if not isinstance(record,dict) or record.get('acquisition_schema')!=1:raise AcquisitionError('resolved acquisition manifest required')
    secret_free(record)
    if type(index)!=int or index<0 or index>=len(record.get('materials',[])):raise AcquisitionError('material index out of range')
    item=record['materials'][index];kind=item.get('kind')
    if kind not in ('pdf','xml','html'):raise AcquisitionError('select an explicit supported fulltext candidate; landing/source/text are not auto-promoted')
    source_url=safe_url(item.get('url'));root=safe_directory(destination)
    identity_hash=hashlib.sha256(str(record['identity']).encode()).hexdigest()[:20]
    folder=safe_directory(root/identity_hash)
    import fcntl
    fd=os.open(folder/'.acquire.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with tempfile.TemporaryDirectory(prefix='.stage-',dir=folder) as stage_name:
            stage=Path(stage_name)
            if local_file is not None:
                file=Path(os.path.abspath(local_file))
                if any(p.is_symlink() for p in [file,*file.parents]):raise AcquisitionError('symlink local input refused')
                fd=os.open(file,os.O_RDONLY|os.O_NOFOLLOW)
                with os.fdopen(fd,'rb') as f:body=f.read(MAX_BYTES+1)
                headers={};final_url=source_url;method='local-file'
            else:body,headers,final_url=(client or SafeHTTP()).get(source_url,MAX_BYTES);method='public-https'
            final_url=safe_url(final_url);format=verify_material(body,kind,headers.get('content-type',''))
            checksum=item.get('checksum')
            if checksum:
                match=re.fullmatch(r'(md5|sha256):([0-9a-fA-F]+)',checksum)
                if not match or len(match[2])!=(32 if match[1]=='md5' else 64):raise AcquisitionError('invalid expected checksum')
                if hashlib.new(match[1],body).hexdigest()!=match[2].lower():raise AcquisitionError('material checksum mismatch')
            digest=hashlib.sha256(body).hexdigest();version=str(item.get('version') or 'unknown')
            binding=hashlib.sha256(json.dumps({'version':version,'url':source_url,'kind':kind},sort_keys=True).encode()).hexdigest()[:12]
            target=folder/(binding+'-'+digest[:20]);name='material.'+kind
            manifest={**record,'state':'fulltext_saved','reading_depth':'metadata','identity_verified':False,
                      'selected_material':{**item,'state':'validated_bytes','actual_format':format,'final_url':final_url,
                                           'sha256':digest,'size':len(body),'local_path':name,'method':method},
                      'saved_at':now(),'review_required':True,'redistribution_permission':'not_assessed'}
            # Byte checks establish material format, never paper identity, truth or reading.
            (stage/name).write_bytes(body);(stage/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
            for file in stage.iterdir():
                with file.open('rb') as f:os.fsync(f.fileno())
            if target.is_symlink():raise AcquisitionError('symlink cache refused')
            if target.exists():
                try:
                    if any(p.is_symlink() for p in target.iterdir()):raise ValueError()
                    old=json.loads((target/'manifest.json').read_text());stored=(target/name).read_bytes()
                    if hashlib.sha256(stored).hexdigest()!=digest or old['selected_material']['sha256']!=digest or old['identity']!=record['identity'] or old['selected_material']['version']!=version:raise ValueError()
                except (OSError,ValueError,KeyError):raise AcquisitionError('existing cache inconsistent; never overwritten') from None
                return target
            os.rename(stage,target)
            # TemporaryDirectory cleanup tolerates stage having been atomically renamed.
            return target

def registration_draft(saved_directory,project,work_id,source_id,paper_id):
    """Produce reviewable journal rows. Never append, migrate or certify reading."""
    project=Path(project).resolve();folder=Path(saved_directory)
    if any(p.is_symlink() for p in [folder,*folder.parents]):raise AcquisitionError('symlink saved input refused')
    folder=folder.resolve()
    try:relative=folder.relative_to(project)
    except ValueError:raise AcquisitionError('saved material must be within target project') from None
    if any(not isinstance(v,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',v) for v in (work_id,source_id,paper_id)):
        raise AcquisitionError('valid explicit work/source/paper IDs required; reuse existing work identity')
    path=folder/'manifest.json'
    if path.is_symlink() or path.stat().st_size>MAX_METADATA:raise AcquisitionError('saved manifest unsafe')
    try:record=json.loads(path.read_text());item=record['selected_material']
    except (ValueError,KeyError):raise AcquisitionError('saved manifest invalid') from None
    secret_free(record)
    name=item.get('local_path')
    if name not in ('material.pdf','material.xml','material.html'):raise AcquisitionError('invalid saved material name')
    artifact=folder/name
    if artifact.is_symlink() or artifact.stat().st_size>MAX_BYTES:raise AcquisitionError('unsafe saved material')
    if hashlib.sha256(artifact.read_bytes()).hexdigest()!=item.get('sha256'):raise AcquisitionError('saved material changed; re-check acquisition')
    if record.get('state')!='fulltext_saved':raise AcquisitionError('validated saved material required')
    stamp=now();source={'schema_version':2,'id':source_id,'rev':1,'updated_at':stamp,
        'url':record['origin_url'],'retrieved_at':record['retrieved_at'],
        'status':'retracted' if record.get('is_retracted') is True else 'active',
        'material_binding':{'path':str(relative/name),'sha256':item['sha256']},
        'acquisition_manifest_binding':{'path':str(relative/'manifest.json'),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},
        'material_kind':item['kind'],'acquisition_state':'fulltext_saved','license':item.get('license'),
        'identity_verified':False,'is_retracted':record.get('is_retracted'),'is_withdrawn':record.get('is_withdrawn'),
        'redistribution_permission':'not_assessed'}
    paper={'schema_version':2,'id':paper_id,'rev':1,'updated_at':stamp,'source_id':source_id,'source_rev':1,
        'work_id':work_id,'title':record['title'],'version':item['version'],'publication_status':record['publication_status'],
        'reading_depth':'metadata','review_status':'needs_review',
        'review_reason':'Acquisition is not reading; verify paper identity, version, status and content before interpreting.'}
    try:paper['doi']=doi(record.get('doi') or record['identity'])
    except AcquisitionError:paper['doi']=None
    return {'state':'registration_draft','source':source,'paper':paper,
        'instructions':'Review IDs, version and DOI relations against existing journals. For existing IDs append next complete rev and pinned source_rev; do not append rev=1 again. Acquisition has not read or verified the paper.'}
