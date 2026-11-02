"""保留逐页 OCR 坐标、置信度、PDF 哈希，识别输出不自动视为人工校对。"""
from pathlib import Path
import fitz,json,time,hashlib,numpy as np
from rapidocr_onnxruntime import RapidOCR
from collect_sources import ROOT

def main():
    sources=json.loads((ROOT/'data/PDF来源清单.json').read_text(encoding='utf-8'))
    sources=[s for s in sources if s['year']<2026 and not (s['year']==2025 and s['kind']=='一等奖' and s['article'].endswith('3772'))]
    out=ROOT/'data/OCR'; out.mkdir(exist_ok=True)
    engine=RapidOCR(det_model_path=None,det_limit_side_len=1600,det_limit_type='max',rec_model_path=None,rec_batch_num=32,intra_op_num_threads=4,inter_op_num_threads=1)
    for s in sources:
        doc=fitz.open(ROOT/s['local'])
        for i,page in enumerate(doc):
            dest=out/f"{s['id']}-p{i+1:02}.json"
            if dest.exists(): continue
            start=time.time()
            pix=page.get_pixmap(matrix=fitz.Matrix(2.5,2.5),alpha=False)
            img=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,3)
            result,_=engine(img)
            data=dict(source=s['id'],pdf_sha256=s['sha256'],page=i+1,width=pix.width,height=pix.height,scale=2.5,
                      engine='RapidOCR PP-OCRv3',boxes=result or [],seconds=round(time.time()-start,2))
            dest.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            print(dest.name,len(result or []),data['seconds'],flush=True)

if __name__=='__main__': main()
