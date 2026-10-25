"""Private native recordings; full reports retained once with chunk hashes/EOF receipts."""
import copy,json,hashlib
from .anonymous_runner import RecordedMCP as BaseRecordedMCP
from .fe_authenticated_contract import save
class RecordedMCP(BaseRecordedMCP):
    def record_response(self,prefix,result):
        if not prefix.endswith('-zap_report_read_chunk'):return super().record_response(prefix,result)
        record=copy.deepcopy(result)
        for block in record.get('content',[]):
            if block.get('type')!='text':continue
            try:
                page=json.loads(block['text'])
                if isinstance(page,str):page=json.loads(page)
                content=page.pop('content');page.update(contentSha256=hashlib.sha256(content.encode()).hexdigest(),contentRef='assembled private reports/native.<format> at recorded offsets',recording='chunk metadata; assembled raw report retained in full')
                block['text']=json.dumps(page)
            except (ValueError,KeyError,TypeError):continue
        save(self.out,prefix+'-response.json',record)
