"""RS256 wire identity plus protected probe; no JWT claim-only admission or network keys."""
import base64,hashlib,json,re,subprocess,tempfile,time
from pathlib import Path
from .product_checks import pointer

VERSION='signed-jwt-protected-probe/1.0'

def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate JWT field')
        result[key]=value
    return result

def decode_segment(text):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',text):raise ValueError('invalid JWT encoding')
    return base64.urlsafe_b64decode(text+'='*((-len(text))%4))

def verify_token(token,trust,mapping,subject,role,*,now=None):
    if not isinstance(token,str) or len(token)>16384:raise ValueError('invalid signed identity token')
    try:
        header,payload,signature=token.split('.')
        h=json.loads(decode_segment(header),object_pairs_hook=unique_object);c=json.loads(decode_segment(payload),object_pairs_hook=unique_object)
        if h.get('alg')!='RS256' or any(k in h for k in ('crit','jku','jwk','x5u','x5c')):raise ValueError('unsupported signed identity algorithm/key source')
        key=Path(trust['publicKey']['path']);blob=key.read_bytes()
        if key.is_symlink() or hashlib.sha256(blob).hexdigest()!=trust['publicKey']['sha256']:raise ValueError('signed identity public key drift')
        size=subprocess.run(['/usr/bin/openssl','pkey','-pubin','-in',str(key),'-text','-noout'],capture_output=True,timeout=5)
        bits=re.search(rb'Public-Key:\s*\((\d+) bit\)',size.stdout)
        if size.returncode or not bits or int(bits[1])<2048:raise ValueError('signed identity requires RSA2048 public key')
        with tempfile.TemporaryDirectory(prefix='zpa-jwt-') as directory:
            sig=Path(directory)/'signature';sig.write_bytes(decode_segment(signature));sig.chmod(0o600)
            checked=subprocess.run(['/usr/bin/openssl','dgst','-sha256','-verify',str(key),'-signature',str(sig)],input=(header+'.'+payload).encode(),capture_output=True,timeout=5)
        if checked.returncode:raise ValueError('signed identity signature mismatch')
        now=time.time() if now is None else now;aud=c.get('aud');aud=[aud] if isinstance(aud,str) else aud
        if c.get('iss')!=mapping['issuer'] or not isinstance(aud,list) or mapping['audience'] not in aud:raise ValueError('signed identity issuer/audience mismatch')
        if c.get('sub')!=str(subject) or c.get(mapping['roleClaim'])!=role:raise ValueError('signed identity subject/role mismatch')
        if type(c.get('iat')) is not int or type(c.get('exp')) is not int or c['iat']>now or not c['iat']<c['exp'] or now>=c['exp'] or ('nbf' in c and (type(c['nbf']) is not int or now<c['nbf'])):raise ValueError('signed identity lifetime invalid')
        return True
    except (KeyError,TypeError,json.JSONDecodeError,UnicodeError,subprocess.SubprocessError) as failure:
        raise ValueError('signed identity malformed or verifier unavailable') from None

def check_probe(status,body,token,trust,mapping,subject,role):
    verify_token(token,trust,mapping,subject,role)
    if status!=mapping['expectedStatus'] or str(pointer(body,mapping['responsePointer']))!=str(mapping['responseValue']):raise ValueError('signed protected probe mismatch')
    return True

def check_native(row,origin,path,trust,mapping,subject,role):
    header=row['requestHeader'];first=header.splitlines()[0].split()
    if len(first)!=3 or first[:2]!=['GET',origin+path]:raise ValueError('signed native identity destination mismatch')
    tokens=re.findall(r'(?im)^Authorization: Bearer ([A-Za-z0-9_.-]+)\r?$',header)
    if len(tokens)!=1 or len(re.findall(r'(?im)^Authorization:',header))!=1:raise ValueError('signed native credential missing/ambiguous')
    if not re.search(r'(?im)^Content-Type: application/json(?:[;\r\n]|$)',row['responseHeader']):raise ValueError('signed native probe not JSON')
    return check_probe(int(row['responseHeader'].split()[1]),json.loads(row['responseBody']),tokens[0],trust,mapping,subject,role)


def check_wire_history(history,origin,identity_path,trust,mapping,subject,role):
    """Audit credentials on actual HTTP observations; retain status0 as unproved coverage."""
    rows=[];excluded=[]
    for message in history:
        header=message.get('requestHeader','');tokens=re.findall(r'(?im)^Authorization: Bearer ([A-Za-z0-9_.-]+)\r?$',header)
        if not tokens:continue
        if len(tokens)!=1 or len(re.findall(r'(?im)^Authorization:',header))!=1:raise ValueError('native wire credential ambiguous')
        status=int(message['responseHeader'].split()[1])
        if status==0:
            excluded.append({'messageId':str(message['id']),'reason':'no HTTP response; history metadata or transport outcome unproved','notWireOrBusinessCoverage':True});continue
        if tokens[0]=='owned-invalid-session' and header.splitlines()[0]=='GET '+origin+identity_path+' HTTP/1.1' and status==401:
            excluded.append({'messageId':str(message['id']),'reason':'declared native invalid-session control','notBusinessCoverage':True});continue
        verify_token(tokens[0],trust,mapping,subject,role)
        rows.append({'messageId':str(message['id']),'subject':str(subject),'role':role,'status':status,'signatureAndClaimsMatched':True})
    if not rows:raise ValueError('signed native HTTP wire evidence missing')
    return {'messages':rows,'excluded':excluded,'coverage':'credential identity on HTTP responses only; business coverage separate'}
