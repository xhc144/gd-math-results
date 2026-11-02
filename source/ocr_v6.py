"""用 PP-OCRv6 独立复识扫描件，保留与第一轮不同的结果。"""
import fitz,json,time,numpy as np,argparse
from rapidocr import RapidOCR
from collect_sources import ROOT

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--part',type=int,default=0); ap.add_argument('--parts',type=int,default=1); args=ap.parse_args()
    sources=json.loads((ROOT/'data/PDF来源清单.json').read_text(encoding='utf-8'))
    sources=[s for s in sources if s['year']<2026 and not (s['year']==2025 and s['kind']=='一等奖' and s['article'].endswith('3772'))]
    out=ROOT/'data/OCRv6'; out.mkdir(exist_ok=True)
    e=RapidOCR(params={'Global.log_level':'error','Det.limit_side_len':1500,'Det.limit_type':'max',
                      'Rec.rec_batch_num':64,'EngineConfig.onnxruntime.intra_op_num_threads':4,
                      'EngineConfig.onnxruntime.inter_op_num_threads':1})
    ix=0
    for s in sources:
        d=fitz.open(ROOT/s['local'])
        for i,p in enumerate(d):
            ix+=1
            if (ix-1)%args.parts!=args.part: continue
            dest=out/f"{s['id']}-p{i+1:02}.json"
            if dest.exists(): continue
            t=time.time(); z=p.get_pixmap(matrix=fitz.Matrix(2.5,2.5),alpha=False)
            a=np.frombuffer(z.samples,np.uint8).reshape(z.height,z.width,3)
            r=e(a)
            boxes=[] if r.boxes is None else [[b.tolist(),txt,float(score)] for b,txt,score in zip(r.boxes,r.txts,r.scores)]
            data=dict(source=s['id'],pdf_sha256=s['sha256'],page=i+1,width=z.width,height=z.height,scale=2.5,
                      engine='RapidOCR 3.10.0 PP-OCRv6 small',boxes=boxes,seconds=round(time.time()-t,2))
            dest.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            print(dest.name,len(boxes),data['seconds'],flush=True)
