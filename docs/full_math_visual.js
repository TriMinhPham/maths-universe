'use strict';
window.FirstbotCharts={render(v){
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 640 420');svg.setAttribute('role','img');svg.setAttribute('aria-label',v.alt);svg.classList.add('math-chart');
 const add=(tag,attrs,text)=>{const e=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,val])=>e.setAttribute(k,String(val)));if(text!==undefined)e.textContent=text;svg.append(e);return e;};
 add('title',{},v.alt);const left=72,right=610,top=45,bottom=340,colors=['#b9f2d6','#ffd590','#b4bcff','#ffb3c7'];
 if(v.type==='comparison'){
  svg.setAttribute('viewBox','0 0 400 260');svg.classList.add('simple-comparison');add('text',{x:200,y:25,'text-anchor':'middle',fill:'#f9f7ed','font-size':19},v.title);const maximum=Math.max(...v.items.map(i=>i.units));
  if(v.orientation==='horizontal')add('line',{x1:65,y1:42,x2:65,y2:230,stroke:'#ecede3','stroke-width':2});else add('line',{x1:55,y1:220,x2:365,y2:220,stroke:'#ecede3','stroke-width':2});
  v.items.forEach((item,i)=>{const horizontal=v.orientation==='horizontal',size=item.units/maximum*(horizontal?270:150);add('rect',horizontal?{x:65,y:60+i*60,width:size,height:30,fill:colors[i]}:{x:80+i*100,y:220-size,width:55,height:size,fill:colors[i]});add('text',horizontal?{x:42,y:82+i*60,'text-anchor':'middle',fill:'#f9f7ed','font-size':20}:{x:107+i*100,y:247,'text-anchor':'middle',fill:'#f9f7ed','font-size':20},item.label);});return svg;
 }
 add('text',{x:320,y:23,'text-anchor':'middle',fill:'#f9f7ed','font-size':17},v.title);
 const xmin=v.type==='plot'?v.x_min:0,xmax=v.type==='plot'?v.x_max:v.categories.length,ymin=v.type==='plot'?v.y_min:0,ymax=v.y_max;
 const X=x=>left+(x-xmin)/(xmax-xmin)*(right-left),Y=y=>bottom-(y-ymin)/(ymax-ymin)*(bottom-top);
 for(let i=0;i<=20;i++){const y=ymin+i*v.y_step;if(y>ymax+1e-8)break;add('line',{x1:left,y1:Y(y),x2:right,y2:Y(y),stroke:'#45606a','stroke-width':1});add('text',{x:left-10,y:Y(y)+5,'text-anchor':'end',fill:'#d3dedc','font-size':15},Number(y.toFixed(6)));}
 if(v.type==='plot'){
  for(let i=0;i<=20;i++){const x=xmin+i*v.x_step;if(x>xmax+1e-8)break;add('line',{x1:X(x),y1:top,x2:X(x),y2:bottom,stroke:'#45606a','stroke-width':1});add('text',{x:X(x),y:bottom+23,'text-anchor':'middle',fill:'#d3dedc','font-size':15},Number(x.toFixed(6)));}
  if(xmin<=0&&xmax>=0)add('line',{x1:X(0),y1:top,x2:X(0),y2:bottom,stroke:'#ecede3','stroke-width':2});
  if(ymin<=0&&ymax>=0)add('line',{x1:left,y1:Y(0),x2:right,y2:Y(0),stroke:'#ecede3','stroke-width':2});
  v.series.forEach((s,i)=>{const color=colors[i];if(s.connect)add('polyline',{points:s.points.map(p=>X(p[0])+','+Y(p[1])).join(' '),fill:'none',stroke:color,'stroke-width':3});if(!s.connect||s.points.length<16)s.points.forEach(p=>add('circle',{cx:X(p[0]),cy:Y(p[1]),r:4,fill:color}));});
 }else{
  const width=(right-left)/v.categories.length,gap=width*.16,bw=(width-gap*2)/v.series.length;
  v.categories.forEach((name,j)=>{add('text',{x:X(j+.5),y:bottom+23,'text-anchor':'middle',fill:'#d3dedc','font-size':14},name);v.series.forEach((s,i)=>add('rect',{x:X(j)+gap+i*bw,y:Y(s.values[j]),width:bw-2,height:bottom-Y(s.values[j]),fill:colors[i]}));});
 }
 add('line',{x1:left,y1:bottom,x2:right,y2:bottom,stroke:'#ecede3','stroke-width':2});add('line',{x1:left,y1:top,x2:left,y2:bottom,stroke:'#ecede3','stroke-width':2});
 add('text',{x:340,y:390,'text-anchor':'middle',fill:'#f9f7ed','font-size':16},v.x_label);add('text',{x:18,y:195,transform:'rotate(-90 18 195)','text-anchor':'middle',fill:'#f9f7ed','font-size':16},v.y_label);
 v.series.forEach((s,i)=>{const x=75+i*140;add('rect',{x,y:402,width:12,height:12,fill:colors[i]});add('text',{x:x+18,y:414,fill:'#f9f7ed','font-size':12},s.label);});return svg;
}};
