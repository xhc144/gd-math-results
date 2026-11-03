from pathlib import Path
import json,fitz,numpy as np,cv2,argparse,time
from rapidocr import RapidOCR
from rapidocr.ch_ppocr_rec.typings import TextRecInput
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--year',type=int,required=True);args=ap.parse_args()
rows=json.loads((ROOT/f'data/报名{args.year}候选.json').read_text(encoding='utf-8'))
meta=json.loads((ROOT/'data/报名来源清单.json').read_text(encoding='utf-8'));s=next(s for s in meta if s['year']==args.year)
doc=fitz.open(ROOT/s['local']);scale=3 if args.year==2020 else 2.5
cache=ROOT/f'data/报名{args.year}单元格.json';results=json.loads(cache.read_text(encoding='utf-8')) if cache.exists() else {}
engine=RapidOCR(params={'Global.log_level':'error','EngineConfig.onnxruntime.intra_op_num_threads':2,'Rec.rec_batch_num':64})
engine(np.full((48,100,3),255,np.uint8),use_det=False,use_cls=False)
todo=[r for r in rows if r['id'] not in results]
for start in range(0,len(todo),32):
    batch=todo[start:start+32];images=[]
    for r in batch:
        page=doc[r['page']-1]
        for key in ['name_box','school_box']:
            x0,y0,x1,y1=r[key];clip=fitz.Rect((x0+2)/scale,(y0+2)/scale,(x1-2)/scale,(y1-2)/scale)
            pix=page.get_pixmap(matrix=fitz.Matrix(scale*1.5,scale*1.5),clip=clip,alpha=False)
            im=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,3).copy()
            images.append(im)
    rec=engine.text_rec(TextRecInput(img=images))
    for i,r in enumerate(batch):
        results[r['id']]=dict(name=rec.txts[i*2],name_confidence=float(rec.scores[i*2]),school=rec.txts[i*2+1],school_confidence=float(rec.scores[i*2+1]))
    cache.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    if start%160==0:print('单元格复识',args.year,start+len(batch),'/',len(todo),flush=True)
print('完成',args.year,len(results))
