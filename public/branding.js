const HEX=/^#[0-9a-f]{6}$/i;
export const validColor=(value,fallback='#f13b30')=>HEX.test(value||'')?value:fallback;
const channels=hex=>[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));
const toHex=rgb=>'#'+rgb.map(v=>Math.round(v).toString(16).padStart(2,'0')).join('');
export function mixColor(first,second,amount){const a=channels(validColor(first)),b=channels(validColor(second));return toHex(a.map((v,i)=>v*(1-amount)+b[i]*amount));}
export function luminance(hex){const c=channels(validColor(hex)).map(v=>v/255).map(v=>v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4);return c[0]*0.2126+c[1]*0.7152+c[2]*0.0722;}
export function readableInk(hex){const light=luminance(hex);return (light+0.05)/0.05>=1.05/(light+0.05)?'#000000':'#ffffff';}
export function paletteFromPixels(pixels){
    const buckets=new Map();
    for(let i=0;i<pixels.length;i+=4){
        const rgb=[pixels[i],pixels[i+1],pixels[i+2]],alpha=pixels[i+3];
        if(alpha<128)continue;
        const max=Math.max(...rgb),min=Math.min(...rgb),delta=max-min;
        // Transparent margins and neutral backgrounds should not dominate the brand.
        if(max>238&&delta<25||max<25||delta<28)continue;
        const hue=((max===rgb[0]?(rgb[1]-rgb[2])/delta:max===rgb[1]?2+(rgb[2]-rgb[0])/delta:4+(rgb[0]-rgb[1])/delta)*60+360)%360;
        const key=Math.floor(hue/15),weight=(delta/max)*(alpha/255);
        const bucket=buckets.get(key)||{weight:0,rgb:[0,0,0]};
        bucket.weight+=weight;bucket.rgb=bucket.rgb.map((v,j)=>v+rgb[j]*weight);buckets.set(key,bucket);
    }
    const colors=[...buckets.values()].sort((a,b)=>b.weight-a.weight).map(b=>b.rgb.map(v=>v/b.weight));
    if(!colors.length)return {primary:'#444444',secondary:'#888888'};
    const primary=toHex(colors[0]);
    const different=colors.slice(1).find(rgb=>Math.hypot(...rgb.map((v,i)=>v-colors[0][i]))>90);
    const secondary=different?toHex(different):mixColor(primary,luminance(primary)>0.4?'#000000':'#ffffff',0.3);
    return {primary,secondary};
}
export async function extractLogoPalette(src){
    if(!/^data:image\/(png|jpeg|webp);base64,/i.test(src||''))throw Error('Selecione uma logo em PNG, JPG ou WebP.');
    const image=new Image();
    await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(Error('Não foi possível ler a logo. Escolha outra imagem.'));image.src=src;});
    const canvas=document.createElement('canvas');canvas.width=96;canvas.height=96;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0,96,96);
    return paletteFromPixels(ctx.getImageData(0,0,96,96).data);
}
export function applyBranding(conf){
    const primary=validColor(conf.brandPrimary),secondary=validColor(conf.brandSecondary,'#2563eb');
    const style=document.documentElement.style;
    const values={'--accent':primary,'--secondary':secondary,'--accent-ink':readableInk(primary),'--secondary-ink':readableInk(secondary),'--accent-soft':primary+'1a','--accent-border':primary+'44','--accent-highlight':mixColor(primary,conf.theme==='light'?'#000000':'#ffffff',conf.theme==='light'?0.2:0.35)};
    for(const [key,value] of Object.entries(values))style.setProperty(key,value);
    document.body.classList.toggle('branded',!!conf.brandPrimary);
    const favicon=document.querySelector('link[rel=icon]');if(favicon)favicon.href=/^data:image\/(png|jpeg|webp);base64,/i.test(conf.logo||'')?conf.logo:'/favicon.svg';
}
