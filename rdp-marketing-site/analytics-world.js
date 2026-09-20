(() => {
  const ns = 'http://www.w3.org/2000/svg';
  const names = new Intl.DisplayNames(['en'], {type:'region'});
  const countryName = code => { try { return code ? names.of(code) || code : 'Unknown'; } catch { return 'Unknown'; } };
  let shapesPromise;
  let revision = 0;
  window.renderWorldTraffic = async data => {
    const ticket = ++revision;
    const section = document.querySelector('[data-world-traffic]');
    if (!section) return;
    const rows = Array.isArray(data.countries) ? data.countries : [];
    const total = Number(data.totals?.visits || 0);
    const unknown = rows.filter(r=>!r.country).reduce((n,r)=>n+Number(r.visits),0);
    const known = rows.filter(r=>r.country);
    section.querySelector('[data-geo-coverage]').textContent = rows.length ? `${known.length} countries / regions · ${total-unknown} located visits · ${unknown} unknown · ${total ? ((total-unknown)*100/total).toFixed(1) : '0'}% coverage` : 'No country data available for this period.';
    const table = section.querySelector('[data-country-table]'); table.replaceChildren();
    for (const row of rows) {
      const tr=document.createElement('tr');
      [countryName(row.country), Number(row.visits).toLocaleString(),Number(row.visitors).toLocaleString(),total ? (Number(row.visits)*100/total).toFixed(1)+'%' : '0%'].forEach(value=>{const td=document.createElement('td');td.textContent=value;tr.append(td);});
      table.append(tr);
    }
    const detail=section.querySelector('[data-geo-detail]');
    detail.textContent = 'Hover or focus a country to see its recorded visits.';
    section.querySelector('[data-geo-source]').textContent = data.geo?.available ? data.geo.edition : 'Local IP database unavailable; known server-provided locations only.';
    try {
      if (!shapesPromise) shapesPromise=fetch('./world-country-shapes.json?v=1').then(r=>{if(!r.ok)throw Error();return r.json();}).catch(e=>{shapesPromise=null;throw e;});
      const shapes=await shapesPromise;
      if(ticket!==revision)return;
      const svg=section.querySelector('svg');svg.replaceChildren();
      const background=document.createElementNS(ns,'path');background.setAttribute('d',shapes.sphere);background.setAttribute('fill','#f1f7ff');svg.append(background);
      const counts=new Map(known.map(r=>[r.country,r]));const max=Math.max(1,...known.map(r=>Number(r.visits)));
      for(const shape of shapes.countries){
        const row=counts.get(shape.code);const count=Number(row?.visits||0);
        const mark=document.createElementNS(ns,'path');mark.setAttribute('d',shape.path);mark.setAttribute('data-country',shape.code);
        const t=count/max;mark.setAttribute('fill',count ? `rgb(${Math.round(190-165*t)},${Math.round(220-100*t)},${Math.round(245-65*t)})` : '#dce4ee');
        mark.setAttribute('stroke','#fff');mark.setAttribute('stroke-width','.55');
        const label=`${shape.code ? countryName(shape.code) : shape.name}: ${count.toLocaleString()} visits`;
        const title=document.createElementNS(ns,'title');title.textContent=label;mark.append(title);
        if(count){mark.setAttribute('tabindex','0');mark.setAttribute('aria-label',label);}
        const show=()=>{detail.textContent=label+(row ? ` · ${Number(row.visitors).toLocaleString()} unique visitor identifiers` : ' recorded in this period');};
        mark.addEventListener('mouseenter',show);mark.addEventListener('focus',show);mark.addEventListener('click',show);svg.append(mark);
      }
      section.querySelector('[data-map-legend]').textContent = `Gray: no recorded visits · Blue: 1–${max.toLocaleString()} visits (linear scale). Small territories may appear only in the table.`;
    }catch{if(ticket===revision)detail.textContent='Map unavailable. Country totals remain available in the table.';}
  };
  window.analyticsCountryName=countryName;
})();
