from pathlib import Path
import json,fitz,numpy as np,argparse,time
from rapidocr import RapidOCR
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--year',type=int,required=True);ap.add_argument('--variant',default='clean',choices=['raw','clean']);a=ap.parse_args()
meta=json.loads((ROOT/'data/报名来源清单.json').read_text(encoding='utf-8'));s=next(s for s in meta if s['year']==a.year)
out=ROOT/f'data/报名OCR/{a.year}-{a.variant}';out.mkdir(parents=True,exist_ok=True)
e=RapidOCR(params={'Global.log_level':'error','Det.limit_side_len':2200 if a.year==2020 else 1500,'Det.limit_type':'max','Rec.rec_batch_num':64,'EngineConfig.onnxruntime.intra_op_num_threads':2,'EngineConfig.onnxruntime.inter_op_num_threads':1})
doc=fitz.open(ROOT/s['local'])
for ix,p in enumerate(doc):
 dest=out/f'p{ix+1:03}.json'
 if dest.exists():continue
 t=time.time();pix=p.get_pixmap(matrix=fitz.Matrix(3 if a.year==2020 else 2.5,3 if a.year==2020 else 2.5),alpha=False);rgb=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,3).copy()
 if a.variant=='clean':rgb[(rgb[:,:,0].astype(float)>rgb[:,:,1]*1.15)&(rgb[:,:,0].astype(float)>rgb[:,:,2]*1.15)]=255
 r=e(rgb);boxes=[] if r.boxes is None else [[b.tolist(),txt,float(sc)] for b,txt,sc in zip(r.boxes,r.txts,r.scores)]
 dest.write_text(json.dumps(dict(page=ix+1,scale=3 if a.year==2020 else 2.5,boxes=boxes),ensure_ascii=False,indent=2),encoding='utf-8')
 if ix%5==0 or ix+1==len(doc):print('报名',a.year,a.variant,ix+1,'/',len(doc),round(time.time()-t,1),flush=True)
