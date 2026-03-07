// ── i18n (Internationalization) ─────────────────────
var currentLang='no';
var translations={};

function t(key, params) {
  var text = translations[key] || key;
  if (params) {
    Object.keys(params).forEach(function(k) {
      text = text.replace(new RegExp('\\{' + k + '\\}', 'g'), params[k]);
    });
  }
  return text;
}

async function loadTranslations(lang) {
  try {
    var data = await api('/api/translations/' + lang);
    if (!data || data.error) return false;
    translations = data;
    currentLang = lang;
    return true;
  } catch(e) { return false; }
}

async function initLanguage() {
  try {
    var data = await api('/api/settings/language');
    currentLang = data.language || 'no';
  } catch(e) { currentLang = 'no'; }
  await loadTranslations(currentLang);
  applyStaticTranslations();
}

function applyStaticTranslations() {
  document.querySelectorAll('[data-i18n]').forEach(function(el) {
    var key = el.getAttribute('data-i18n');
    el.textContent = t(key);
  });
  document.querySelectorAll('[data-i18n-html]').forEach(function(el) {
    var key = el.getAttribute('data-i18n-html');
    el.innerHTML = t(key);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(function(el) {
    var key = el.getAttribute('data-i18n-placeholder');
    el.placeholder = t(key);
  });
  document.querySelectorAll('[data-i18n-title]').forEach(function(el) {
    var key = el.getAttribute('data-i18n-title');
    el.title = t(key);
  });
  // Update html lang attribute
  document.documentElement.lang = currentLang;
}

async function changeLanguage(lang) {
  var ok = await loadTranslations(lang);
  if (!ok) return;
  await api('/api/settings/language', {method:'PUT', body:JSON.stringify({language:lang})});
  applyStaticTranslations();
  // Reload dynamic content
  if (currentView === 'settings') loadSettings();
  else loadData();
}

var currentView='search',currentFilter=[],expandedId=null,editingId=null;
var searchTimeout=null,cachedStats=null,cachedResults=[];
var sortCol='total_score',sortDir='desc';
var categories=[];
var imageCache={};

// All nutrition field IDs used in register/edit forms
var NUTRI_IDS=['kcal','energy_kj','fat','saturated_fat','carbs','sugar','protein','fiber','salt','weight','portion'];

function catEmoji(typeName){var c=categories.find(function(x){return x.name===typeName});return c?c.emoji:'\u{1F4E6}';}
function catLabel(typeName){var c=categories.find(function(x){return x.name===typeName});return c?c.label:typeName;}
function esc(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML;}
function safeDataUri(uri){if(typeof uri!=='string')return '';if(/^data:image\/(png|jpeg|jpg|gif|webp|svg\+xml);base64,[A-Za-z0-9+/=]+$/.test(uri))return uri;if(/^https?:\/\//.test(uri))return esc(uri);return '';}
function fmtNum(v){if(v==null)return '-';return parseFloat(v).toFixed(v%1?1:0);}

async function api(path,opts){opts=opts||{};var res=await fetch(path,Object.assign({headers:{'Content-Type':'application/json'}},opts));return res.json();}
async function fetchProducts(search,types){var p=new URLSearchParams();if(search)p.set('search',search);if(types&&types.length)p.set('type',types.join(','));return api('/api/products?'+p);}
async function fetchStats(){cachedStats=await api('/api/stats');categories=cachedStats.categories||[];document.getElementById('stats-line').textContent=t('stats_line',{total:cachedStats.total,types:cachedStats.types});buildTypeSelect();}

function buildFilters(){if(!cachedStats)return;var row=document.getElementById('filter-row');var h='<button class="pill '+(currentFilter.length===0?'active':'')+'" onclick="setFilter(\'all\')">'+t('filter_all')+' ('+cachedStats.total+')</button>';categories.forEach(function(c){var n=cachedStats.type_counts[c.name]||0;var active=currentFilter.indexOf(c.name)>=0;h+='<button class="pill '+(active?'active':'')+'" onclick="setFilter(\''+esc(c.name)+'\')">'+esc(c.emoji)+' '+esc(c.label)+' ('+n+')</button>';});row.innerHTML=h;updateFilterToggle();}
function updateFilterToggle(){var tog=document.getElementById('filter-toggle');var label=document.getElementById('filter-toggle-label');if(!tog)return;if(currentFilter.length>0){var names=currentFilter.map(function(f){var cat=categories.find(function(c){return c.name===f;});return cat?(cat.emoji+' '+cat.label):f;});label.textContent=names.length<=2?names.join(', '):t('filter_count',{count:names.length});tog.classList.add('has-filter');}else{label.textContent=t('filter_all');tog.classList.remove('has-filter');}}
function toggleFilters(){var row=document.getElementById('filter-row');var tog=document.getElementById('filter-toggle');row.classList.toggle('open');tog.classList.toggle('open');}
function buildTypeSelect(){var sel=document.getElementById('f-type');var prev=sel.value;sel.innerHTML='';categories.forEach(function(c){var o=document.createElement('option');o.value=c.name;o.textContent=c.emoji+' '+c.label;sel.appendChild(o);});if(prev){for(var i=0;i<sel.options.length;i++){if(sel.options[i].value===prev){sel.value=prev;break;}}}}

function sortIndicator(col){if(sortCol!==col)return '<span class="sort-arrow dim">\u2195</span>';return sortDir==='asc'?'<span class="sort-arrow">\u2191</span>':'<span class="sort-arrow">\u2193</span>';}
function setSort(col){if(sortCol===col){sortDir=sortDir==='desc'?'asc':'desc';}else{sortCol=col;sortDir=col==='name'?'asc':'desc';}rerender();}
function applySorting(res){return res.slice().sort(function(a,b){var va=a[sortCol],vb=b[sortCol];if(typeof va==='string'||typeof vb==='string'){va=(va||'').toLowerCase();vb=(vb||'').toLowerCase();return sortDir==='asc'?va.localeCompare(vb):vb.localeCompare(va);}if(va==null)va=sortDir==='asc'?Infinity:-Infinity;if(vb==null)vb=sortDir==='asc'?Infinity:-Infinity;return sortDir==='asc'?va-vb:vb-va;});}
function rerender(){renderResults(cachedResults,document.getElementById('search-input').value.trim());}

// ── Image handling ──────────────────────────────────
async function loadProductImage(id){
  if(imageCache[id]!==undefined)return imageCache[id];
  try{var res=await fetch('/api/products/'+id+'/image');if(!res.ok){imageCache[id]=null;return null;}var d=await res.json();imageCache[id]=d.image;return d.image;}catch(e){imageCache[id]=null;return null;}
}

function triggerImageUpload(id){
  var inp=document.createElement('input');inp.type='file';inp.accept='image/*';
  inp.onchange=async function(){
    if(!inp.files.length)return;
    var file=inp.files[0];
    if(file.size>10*1024*1024){showToast(t('toast_image_too_large'),'error');return;}
    var reader=new FileReader();
    reader.onload=async function(e){
      var resized=await resizeImage(e.target.result,400);
      try{
        await api('/api/products/'+id+'/image',{method:'PUT',body:JSON.stringify({image:resized})});
        imageCache[id]=resized;
        var p=cachedResults&&cachedResults.find(function(x){return x.id===id;});
        if(p)p.has_image=1;
        showToast(t('toast_image_saved'),'success');rerender();
      }catch(err){showToast(t('toast_image_upload_error'),'error');}
    };reader.readAsDataURL(file);
  };inp.click();
}

function resizeImage(dataUri,maxSize){
  return new Promise(function(resolve){
    var img=new Image();img.onload=function(){
      var w=img.width,h=img.height;
      if(w<=maxSize&&h<=maxSize){resolve(dataUri);return;}
      var ratio=Math.min(maxSize/w,maxSize/h);
      var canvas=document.createElement('canvas');canvas.width=w*ratio;canvas.height=h*ratio;
      var ctx=canvas.getContext('2d');ctx.drawImage(img,0,0,canvas.width,canvas.height);
      resolve(canvas.toDataURL('image/jpeg',0.85));
    };img.src=dataUri;
  });
}

async function removeProductImage(id){
  if(!confirm('Remove image?'))return;
  await api('/api/products/'+id+'/image',{method:'DELETE'});
  imageCache[id]=null;
  var p=cachedResults&&cachedResults.find(function(x){return x.id===id;});
  if(p)p.has_image=0;
  showToast(t('toast_image_removed'),'success');rerender();
}

// ── Render ──────────────────────────────────────────
function renderNutriTable(p){
  var rows=[
    [t('nutri_energy')+' (kcal)',p.kcal,'kcal'],
    [t('nutri_energy')+' (kJ)',p.energy_kj,'kJ'],
    [t('nutri_fat'),p.fat,'g'],
    ['  '+t('nutri_saturated'),p.saturated_fat,'g',true],
    [t('nutri_carbs'),p.carbs,'g'],
    ['  '+t('nutri_sugar'),p.sugar,'g',true],
    [t('nutri_protein'),p.protein,'g'],
    [t('nutri_fiber'),p.fiber,'g'],
    [t('nutri_salt'),p.salt,'g'],
  ];
  var h='<table class="nutri-table">';
  rows.forEach(function(r){
    var isSub=r[3];
    var val=r[1];
    var display=(val!=null)?parseFloat(val).toFixed(r[2]==='g'?1:0)+' '+r[2]:'-';
    h+='<tr'+(isSub?' class="sub"':'')+'><td>'+r[0]+'</td><td>'+display+'</td></tr>';
  });
  if(p.est_pdcaas||p.est_diaas){
    if(p.est_pdcaas)h+='<tr><td style="color:#00e5cc">PDCAAS <span style="font-size:9px;opacity:0.5">(est.)</span></td><td style="color:#00e5cc;font-family:\'Space Mono\',monospace">'+parseFloat(p.est_pdcaas).toFixed(2)+'</td></tr>';
    if(p.est_diaas)h+='<tr><td style="color:#00bfff">DIAAS <span style="font-size:9px;opacity:0.5">(est.)</span></td><td style="color:#00bfff;font-family:\'Space Mono\',monospace">'+parseFloat(p.est_diaas).toFixed(2)+'</td></tr>';
  }
  h+='</table>';
  var extras=[];
  if(p.weight)extras.push(t('extra_weight',{val:p.weight}));
  if(p.portion)extras.push(t('extra_portion',{val:p.portion}));
  if(p.price)extras.push(t('extra_price',{val:p.price}));
  if(p.volume)extras.push(t('extra_volume',{val:p.volume}));
  if(extras.length)h+='<div style="margin-top:8px;font-size:11px;color:rgba(255,255,255,0.3)">'+extras.join(' \u00B7 ')+'</div>';
  return h;
}

// ── Dynamic column helpers ──────────────────────────
var COL_UNITS={kcal:'',energy_kj:'',carbs:'g',sugar:'g',fat:'g',saturated_fat:'g',protein:'g',fiber:'g',salt:'g',taste_score:'',volume:'',price:'kr'};
function fmtCell(field,val){
  if(val==null)return '-';
  if(field==='taste_score'){var st='\u2605'.repeat(Math.round(val)),dm='\u2605'.repeat(6-Math.round(val));return '<span class="stars">'+st+'<span class="stars-dim">'+dm+'</span></span>';}
  if(field==='price')return val?val.toFixed(0)+'kr':'-';
  var u=COL_UNITS[field]||'';
  if(field==='salt')return val.toFixed(2)+u;
  if(field==='kcal'||field==='energy_kj')return Math.round(val)+u;
  return parseFloat(val).toFixed(1)+u;
}
function getActiveCols(){
  var cols=[{key:'name',label:t('col_product'),width:'2.4fr'}];
  var enabled=weightData.filter(function(w){return w.enabled;});
  var isMobile=window.innerWidth<640;
  if(!isMobile){
    enabled.forEach(function(w){cols.push({key:w.field,label:w.label,width:'0.7fr'});});
  }
  cols.push({key:'total_score',label:t('col_score'),width:'0.9fr'});
  return cols;
}
function getGridTemplate(cols){return cols.map(function(c){return c.width;}).join(' ');}

// Re-render on resize (debounced)
var _resizeTimer=null;
window.addEventListener('resize',function(){clearTimeout(_resizeTimer);_resizeTimer=setTimeout(function(){if(editingId===null)rerender();},200);});

function renderResults(results,search){
  cachedResults=results;
  document.getElementById('result-count').textContent=search?(results.length!==1?t('result_count_search_plural',{count:results.length,query:search}):t('result_count_search',{count:results.length,query:search})):(results.length!==1?t('result_count_plural',{count:results.length}):t('result_count',{count:results.length}));
  var container=document.getElementById('results-container');
  if(!results.length){container.innerHTML='<div class="empty"><div class="empty-icon">\u{1F50D}</div><p>'+t('no_products_found')+'</p></div>';return;}
  var sorted=applySorting(results);
  var cols=getActiveCols();
  var gridTpl=getGridTemplate(cols);
  var h='<div class="table-wrap"><div class="table-head" style="grid-template-columns:'+gridTpl+'">';
  cols.forEach(function(c,i){h+='<span class="th-sort'+(sortCol===c.key?' th-active':'')+'" onclick="setSort(\''+c.key+'\')"'+(i>0?' style="text-align:right"':'')+'>'+c.label+' '+sortIndicator(c.key)+'</span>';});
  h+='</div>';
  sorted.forEach(function(p){
    var hasImg=p.has_image;
    var thumbHtml=hasImg?'<img class="prod-thumb" id="thumb-'+p.id+'" src="" alt="">':'';
    var eanHtml=p.ean?'<span class="prod-ean">EAN: '+esc(p.ean)+'</span>':'';
    var brandHtml=p.brand?'<span style="color:rgba(255,255,255,0.3)">'+esc(p.brand)+'</span>':'';
    h+='<div class="table-row" style="grid-template-columns:'+gridTpl+'" onclick="toggleExpand('+p.id+')">'
      +'<div><div style="display:flex;align-items:center;gap:8px"><span style="font-size:14px">'+catEmoji(p.type)+'</span>'+thumbHtml+'<span class="prod-name">'+esc(p.name)+'</span></div>'
      +'<div class="prod-meta"><span>'+catLabel(p.type)+'</span>'+brandHtml+eanHtml+'</div></div>';
    for(var ci=1;ci<cols.length;ci++){
      var c=cols[ci];
      if(c.key==='total_score'){h+='<span class="cell-score">'+p.total_score.toFixed(1)+(p.has_missing_scores?'<span style="color:#f5a623;margin-left:1px" title="Score based on incomplete data — some values are 0 or missing">*</span>':'')+'</span>';}
      else{h+='<span class="cell-right">'+fmtCell(c.key,p[c.key])+'</span>';}
    }
    h+='</div>';
    if(expandedId===p.id){
      h+='<div class="expanded"><div class="expanded-top">'
        +'<div class="expanded-img-area" onclick="event.stopPropagation();triggerImageUpload('+p.id+')">'
        +'<div id="prod-img-wrap-'+p.id+'">'+(hasImg?'<img id="prod-img-'+p.id+'" src="" style="width:100%;height:100%;object-fit:cover">':'<div class="expanded-img-placeholder">\u{1F4F7}</div>')+'</div>'
        +'<div class="expanded-img-overlay">'+(hasImg?t('expanded_change_image'):t('expanded_upload_image'))+'</div></div>'
        +'<div class="expanded-right">';
      h+='<p class="expanded-title">'+t('expanded_score_breakdown')+'</p><div class="score-grid">';
      var sc=p.scores||{};
      for(var sf in sc){
        var scfg=SCORE_CFG_MAP[sf];
        if(!scfg)continue;
        var sv=sc[sf];
        var pct=Math.min(sv,100);
        var col=SCORE_COLORS[sf]||'#888';
        h+='<div><div class="score-label">'+scfg.label+'</div><div class="score-bar-bg"><div class="score-bar-fill" style="width:'+pct+'%;background:'+col+'"></div></div><span class="score-val">'+sv.toFixed(1)+'</span></div>';
      }
      if(!Object.keys(sc).length)h+='<div style="color:rgba(255,255,255,0.3);font-size:12px;grid-column:1/-1">'+t('expanded_no_weights')+'</div>';
      h+='</div>';
      if(p.has_missing_scores&&p.missing_fields&&p.missing_fields.length){
        var mLabels=p.missing_fields.map(function(f){var c=SCORE_CFG_MAP[f];return c?c.label:f;}).join(', ');
        h+='<div style="margin-top:8px;padding:8px 10px;border-radius:7px;background:rgba(245,166,35,0.08);border:1px solid rgba(245,166,35,0.18);font-size:11px;color:rgba(245,166,35,0.85)"><span style="margin-right:4px">⚠</span> '+t('expanded_missing_data',{fields:esc(mLabels)})+'</div>';
      }
      // Nutrition table
      h+='<p class="nutri-section-title">'+t('expanded_nutrition_title')+'</p>';
      h+=renderNutriTable(p);
      if(p.brand||p.stores||p.ingredients){
        h+='<p class="nutri-section-title">'+t('expanded_product_info')+'</p>';
        if(p.brand)h+='<div style="margin-bottom:5px"><span style="font-size:10px;color:rgba(255,255,255,0.35)">'+t('expanded_label_brand')+'</span><span style="font-size:12px;color:rgba(255,255,255,0.7)">'+esc(p.brand)+'</span></div>';
        if(p.stores)h+='<div style="margin-bottom:5px"><span style="font-size:10px;color:rgba(255,255,255,0.35)">'+t('expanded_label_stores')+'</span><span style="font-size:12px;color:rgba(255,255,255,0.7)">'+esc(p.stores)+'</span></div>';
        if(p.ingredients)h+='<div style="margin-top:4px"><span style="font-size:10px;color:rgba(255,255,255,0.35);display:block;margin-bottom:3px">'+t('expanded_label_ingredients')+'</span><span style="font-size:11px;color:rgba(255,255,255,0.5);line-height:1.5">'+esc(p.ingredients)+'</span></div>';
      }
      h+='</div></div>';

      if(editingId===p.id){
        var opts='';categories.forEach(function(c){opts+='<option value="'+esc(c.name)+'"'+(c.name===p.type?' selected':'')+'>'+esc(c.emoji)+' '+esc(c.label)+'</option>';});
        h+='<div class="edit-form"><div class="edit-grid">'
          +'<div class="edit-grid-2"><label>'+t('edit_label_name')+'</label><input id="ed-name" value="'+esc(p.name)+'" oninput="validateOffBtn(\'ed\')"></div>'
          +'<div><label>'+t('edit_label_ean')+'</label><div class="ean-row"><div><input id="ed-ean" value="'+esc(p.ean||'')+'" oninput="validateOffBtn(\'ed\')"></div><button class="btn-scan" onclick="event.stopPropagation();openScanner(\'ed\','+p.id+')" title="'+t('btn_scan_title')+'">&#128247;</button><button class="btn-off" id="ed-off-btn" '+((isValidEan(p.ean)||p.name.trim())?'':'disabled')+' onclick="event.stopPropagation();lookupOFF(\'ed\','+p.id+')"><span class="off-spin"></span><span class="off-label">'+ t('btn_fetch')+'</span></button></div></div>'
          +'<div><label>'+t('edit_label_category')+'</label><select id="ed-type">'+opts+'</select></div>'
          +'<div><label>'+t('edit_label_brand')+'</label><input id="ed-brand" value="'+esc(p.brand||'')+'"></div>'
          +'<div><label>'+t('edit_label_stores')+'</label><input id="ed-stores" value="'+esc(p.stores||'')+'"></div>'
          +'<div class="edit-grid-2"><label>'+t('edit_label_ingredients')+'</label><textarea id="ed-ingredients" rows="2" style="resize:vertical;min-height:50px;width:100%;padding:7px 9px;border-radius:7px;border:1px solid rgba(255,255,255,0.08);background:rgba(255,255,255,0.04);color:#e8e6e3;font-size:13px;font-family:\'DM Sans\',sans-serif;outline:none" oninput="updateEstimateBtn(\'ed\')">'+esc(p.ingredients||'')+'</textarea></div>';
      function ev(v){return v==null?'':v;}
      h+='<div><label>'+t('edit_label_kcal')+'</label><input type="number" step="1" id="ed-kcal" value="'+ev(p.kcal)+'"></div>'
          +'<div><label>'+t('edit_label_energy_kj')+'</label><input type="number" step="1" id="ed-energy_kj" value="'+ev(p.energy_kj)+'"></div>'
          +'<div><label>'+t('edit_label_fat')+'</label><input type="number" step="0.1" id="ed-fat" value="'+ev(p.fat)+'"></div>'
          +'<div><label>'+t('edit_label_saturated_fat')+'</label><input type="number" step="0.1" id="ed-saturated_fat" value="'+ev(p.saturated_fat)+'"></div>'
          +'<div><label>'+t('edit_label_carbs')+'</label><input type="number" step="0.1" id="ed-carbs" value="'+ev(p.carbs)+'"></div>'
          +'<div><label>'+t('edit_label_sugar')+'</label><input type="number" step="0.1" id="ed-sugar" value="'+ev(p.sugar)+'"></div>'
          +'<div><label>'+t('edit_label_protein')+'</label><input type="number" step="0.1" id="ed-protein" value="'+ev(p.protein)+'"></div>'
          +'<div><label>'+t('edit_label_fiber')+'</label><input type="number" step="0.1" id="ed-fiber" value="'+ev(p.fiber)+'"></div>'
          +'<div><label>'+t('edit_label_salt')+'</label><input type="number" step="0.01" id="ed-salt" value="'+ev(p.salt)+'"></div>'
          +'<div><label>'+t('edit_label_weight')+'</label><input type="number" step="1" id="ed-weight" value="'+ev(p.weight)+'"></div>'
          +'<div><label>'+t('edit_label_portion')+'</label><input type="number" step="1" id="ed-portion" value="'+ev(p.portion)+'"></div>'
          +'<div><label>'+t('edit_label_volume')+'</label><input type="number" step="0.1" id="ed-volume" value="'+ev(p.volume)+'"></div>'
          +'<div><label>'+t('edit_label_price')+'</label><input type="number" step="1" id="ed-price" value="'+ev(p.price)+'"></div>'
          +'<div><label>'+t('edit_label_taste')+'</label><input type="number" step="0.5" min="0" max="6" id="ed-smak" value="'+ev(p.taste_score)+'"></div>'
          +'</div>'
          +(p.ingredients
            ?'<div style="display:flex;align-items:center;justify-content:space-between;margin:10px 0 4px">'
              +'<span style="font-size:9px;color:rgba(255,255,255,0.35);text-transform:uppercase;letter-spacing:0.06em;font-family:\'Space Mono\',monospace">Protein quality (estimated)</span>'
              +'<button type="button" class="btn-off" id="ed-estimate-btn" onclick="event.stopPropagation();estimateProteinQuality(\'ed\')" style="font-size:11px;padding:5px 10px"><span class="off-spin"></span><span class="off-label">&#9881; Estimate</span></button></div>'
              +'<div id="ed-pq-result" style="'+(p.est_pdcaas||p.est_diaas?'':'display:none;')+'padding:10px;border-radius:8px;background:rgba(0,229,204,0.06);border:1px solid rgba(0,229,204,0.15);margin-bottom:8px">'
              +'<div style="display:flex;gap:16px;margin-bottom:4px"><span style="font-size:11px;color:rgba(255,255,255,0.4)">PDCAAS: <span id="ed-pdcaas-val" style="color:#00e5cc;font-weight:700;font-family:\'Space Mono\',monospace">'+(p.est_pdcaas?parseFloat(p.est_pdcaas).toFixed(2):'–')+'</span></span>'
              +'<span style="font-size:11px;color:rgba(255,255,255,0.4)">DIAAS: <span id="ed-diaas-val" style="color:#00bfff;font-weight:700;font-family:\'Space Mono\',monospace">'+(p.est_diaas?parseFloat(p.est_diaas).toFixed(2):'–')+'</span></span></div>'
              +'<div id="ed-pq-sources" style="font-size:10px;color:rgba(255,255,255,0.3)"></div></div>'
            :'')
          +'<input type="hidden" id="ed-est_pdcaas" value="'+(p.est_pdcaas!=null?p.est_pdcaas:'')+'">'
          +'<input type="hidden" id="ed-est_diaas" value="'+(p.est_diaas!=null?p.est_diaas:'')+'">'
          +'<div style="display:flex;gap:8px">'
          +'<button class="btn-sm btn-green" onclick="event.stopPropagation();saveProduct('+p.id+')">'+t('btn_save')+'</button>'
          +'<button class="btn-sm btn-outline" onclick="event.stopPropagation();editingId=null;rerender()">'+t('btn_cancel')+'</button>'
          +'</div></div>';
      } else {
        h+='<div class="expanded-actions">'
          +'<button class="btn-sm btn-outline" onclick="event.stopPropagation();startEdit('+p.id+')">'+t('btn_edit')+'</button>';
        if(hasImg)h+='<button class="btn-sm btn-outline" onclick="event.stopPropagation();removeProductImage('+p.id+')">'+t('btn_remove_image')+'</button>';
        h+='<button class="btn-sm btn-red" onclick="event.stopPropagation();deleteProduct('+p.id+',\''+esc(p.name).replace(/'/g,"\\\'")+'\')">'+t('btn_delete')+'</button>'
          +'</div>';
      }
      h+='</div>';
    }
  });
  h+='</div>';container.innerHTML=h;
  sorted.forEach(function(p){
    if(p.has_image){
      loadProductImage(p.id).then(function(dataUri){
        if(!dataUri)return;
        var thumb=document.getElementById('thumb-'+p.id);if(thumb)thumb.src=dataUri;
        var full=document.getElementById('prod-img-'+p.id);if(full)full.src=dataUri;
      });
    }
  });
}

function startEdit(id){editingId=id;rerender();}
async function saveProduct(id){
  function numOrNull(id){var v=document.getElementById(id).value;return v===''?null:+v;}
  var data={
    name:document.getElementById('ed-name').value.trim(),
    type:document.getElementById('ed-type').value,
    ean:document.getElementById('ed-ean').value.trim(),
    brand:(document.getElementById('ed-brand')||{value:''}).value.trim(),
    stores:(document.getElementById('ed-stores')||{value:''}).value.trim(),
    ingredients:(document.getElementById('ed-ingredients')||{value:''}).value.trim(),
    taste_score:numOrNull('ed-smak'),
    kcal:numOrNull('ed-kcal'),
    energy_kj:numOrNull('ed-energy_kj'),
    fat:numOrNull('ed-fat'),
    saturated_fat:numOrNull('ed-saturated_fat'),
    carbs:numOrNull('ed-carbs'),
    sugar:numOrNull('ed-sugar'),
    protein:numOrNull('ed-protein'),
    fiber:numOrNull('ed-fiber'),
    salt:numOrNull('ed-salt'),
    weight:numOrNull('ed-weight'),
    portion:numOrNull('ed-portion'),
    volume:numOrNull('ed-volume'),
    price:numOrNull('ed-price'),
    est_pdcaas:numOrNull('ed-est_pdcaas'),
    est_diaas:numOrNull('ed-est_diaas'),
  };
  if(!data.name){showToast(t('toast_name_required'),'error');return;}
  await api('/api/products/'+id,{method:'PUT',body:JSON.stringify(data)});
  editingId=null;showToast(t('toast_product_updated'),'success');loadData();
}
async function deleteProduct(id,name){
  if(!confirm(t('confirm_delete_product',{name:name})))return;
  await api('/api/products/'+id,{method:'DELETE'});
  delete imageCache[id];expandedId=null;editingId=null;showToast(t('toast_product_deleted',{name:name}),'error');loadData();
}

async function loadData(){await fetchStats();buildFilters();var search=currentView==='search'?document.getElementById('search-input').value.trim():'';var results=await fetchProducts(search,currentFilter);renderResults(results,search);}
function switchView(v){currentView=v;expandedId=null;editingId=null;document.querySelectorAll('.nav-tab').forEach(function(t){t.classList.toggle('active',t.dataset.view===v);});document.getElementById('view-search').style.display=v==='search'?'':'none';document.getElementById('view-register').style.display=v==='register'?'':'none';document.getElementById('view-settings').style.display=v==='settings'?'':'none';if(v==='settings')loadSettings();else loadData();if(v==='search')document.getElementById('search-input').focus();}
function setFilter(f){if(f==='all'){currentFilter=[];}else{var i=currentFilter.indexOf(f);if(i>=0)currentFilter.splice(i,1);else currentFilter.push(f);}buildFilters();loadData();}
function toggleExpand(id){expandedId=(expandedId===id)?null:id;editingId=null;rerender();}
function onSearchInput(){var v=document.getElementById('search-input').value;document.getElementById('search-clear').classList.toggle('visible',v.length>0);expandedId=null;editingId=null;clearTimeout(searchTimeout);searchTimeout=setTimeout(loadData,250);}
function clearSearch(){document.getElementById('search-input').value='';document.getElementById('search-clear').classList.remove('visible');expandedId=null;editingId=null;loadData();document.getElementById('search-input').focus();}
function showToast(msg,type){var t=document.getElementById('toast');t.textContent=msg;t.className='toast '+type+' show';setTimeout(function(){t.classList.remove('show');},3000);}

async function registerProduct(){
  var name=document.getElementById('f-name').value.trim();
  if(!name){showToast(t('toast_product_name_required'),'error');return;}
  var btn=document.getElementById('btn-submit');btn.disabled=true;btn.textContent=t('toast_saving');
  function numOrNull(id){var v=document.getElementById(id).value;return v===''?null:+v;}
  try{
    var body={
      type:document.getElementById('f-type').value,
      name:name,
      ean:document.getElementById('f-ean').value.trim(),
      brand:document.getElementById('f-brand').value.trim(),
      stores:document.getElementById('f-stores').value.trim(),
      ingredients:document.getElementById('f-ingredients').value.trim(),
      taste_score:numOrNull('f-smak'),
      kcal:numOrNull('f-kcal'),
      energy_kj:numOrNull('f-energy_kj'),
      fat:numOrNull('f-fat'),
      saturated_fat:numOrNull('f-saturated_fat'),
      carbs:numOrNull('f-carbs'),
      sugar:numOrNull('f-sugar'),
      protein:numOrNull('f-protein'),
      fiber:numOrNull('f-fiber'),
      salt:numOrNull('f-salt'),
      weight:numOrNull('f-weight'),
      portion:numOrNull('f-portion'),
      volume:numOrNull('f-volume'),
      price:numOrNull('f-price'),
      est_pdcaas:numOrNull('f-est_pdcaas'),
      est_diaas:numOrNull('f-est_diaas'),
    };
    var registeredType=body.type;
    var result=await api('/api/products',{method:'POST',body:JSON.stringify(body)});
    var newProductId=result.id;
    if(window._pendingImage&&newProductId){
      try{await api('/api/products/'+newProductId+'/image',{method:'PUT',body:JSON.stringify({image:window._pendingImage})});}catch(ie){}
      window._pendingImage=null;
    }
    document.getElementById('f-name').value='';document.getElementById('f-ean').value='';
    document.getElementById('f-brand').value='';document.getElementById('f-stores').value='';document.getElementById('f-ingredients').value='';
    document.getElementById('f-est_pdcaas').value='';document.getElementById('f-est_diaas').value='';
    var pqw=document.getElementById('f-protein-quality-wrap');if(pqw)pqw.style.display='none';
    var pqr=document.getElementById('f-pq-result');if(pqr)pqr.style.display='none';
    validateOffBtn('f');
    NUTRI_IDS.forEach(function(id){document.getElementById('f-'+id).value='';});
    document.getElementById('f-volume').value='';document.getElementById('f-price').value='';
    document.getElementById('f-smak').value='3';document.getElementById('smak-val').textContent='3';
    showToast(t('toast_product_added',{name:name}),'success');

    // Switch to search view filtered by the registered category
    currentFilter=[registeredType];
    switchView('search');
    // Open filters to show selected category
    var filterRow=document.getElementById('filter-row');
    var filterTog=document.getElementById('filter-toggle');
    if(filterRow&&!filterRow.classList.contains('open')){filterRow.classList.add('open');if(filterTog)filterTog.classList.add('open');}
    // Clear search input
    document.getElementById('search-input').value='';
    document.getElementById('search-clear').classList.remove('visible');
    // Wait for data to load, then scroll to and highlight the new product
    await fetchStats();buildFilters();
    var filtered=await fetchProducts('',currentFilter);
    renderResults(filtered,'');
    if(newProductId){
      setTimeout(function(){
        var rowEl=document.querySelector('.table-row[onclick="toggleExpand('+newProductId+')"]');
        if(rowEl){
          rowEl.classList.add('scan-highlight');
          rowEl.scrollIntoView({behavior:'smooth',block:'center'});
          setTimeout(function(){rowEl.classList.remove('scan-highlight');},5000);
        }
      },200);
    }
  }catch(e){showToast(t('toast_save_error'),'error');}
  btn.disabled=false;btn.textContent=t('btn_register_product');
}

// ── Weights (dynamic) ───────────────────────────────
var SCORE_COLORS={
  kcal:'#aa66ff',energy_kj:'#9955ee',carbs:'#ff44aa',sugar:'#ff66cc',
  fat:'#ff8844',saturated_fat:'#ffaa66',protein:'#00d4ff',fiber:'#44ff88',
  salt:'#ff4444',taste_score:'#E8B84B',volume:'#ff8800',price:'#ff6600',
  est_pdcaas:'#00e5cc',est_diaas:'#00bfff'
};
var SCORE_CFG_MAP={};
var weightData=[];

async function loadSettings(){
  document.getElementById('settings-loading').style.display='';document.getElementById('settings-content').style.display='none';
  try{
    weightData=await api('/api/weights');
    SCORE_CFG_MAP={};
    weightData.forEach(function(w){SCORE_CFG_MAP[w.field]={label:w.label,direction:w.direction,formula:w.formula,formula_min:w.formula_min,formula_max:w.formula_max};});
    renderWeightItems();
  }catch(e){showToast(t('toast_load_error'),'error');}
  document.getElementById('settings-loading').style.display='none';document.getElementById('settings-content').style.display='';
  // Populate language dropdown dynamically
  var langSelect=document.getElementById('language-select');
  if(langSelect){
    try{
      var langs=await api('/api/languages');
      langSelect.innerHTML='';
      langs.forEach(function(l){
        var opt=document.createElement('option');
        opt.value=l.code;
        opt.textContent=(l.flag?l.flag+' ':'')+l.label;
        langSelect.appendChild(opt);
      });
    }catch(e){}
    langSelect.value=currentLang;
  }
  loadCategories();
  loadPq();
}

function renderWeightItems(){
  var container=document.getElementById('weight-items');
  var h='';
  weightData.forEach(function(w,i){
    var ena=w.enabled;
    var col=SCORE_COLORS[w.field]||'#888';
    var dirLower=w.direction==='lower';
    var isDirect=w.formula==='direct';
    var desc=dirLower?t('direction_lower_desc',{label:w.label.toLowerCase()}):t('direction_higher_desc',{label:w.label.toLowerCase()});
    if(isDirect)desc+=' (fixed max: '+w.formula_max+')';
    h+='<div class="weight-item '+(ena?'enabled':'disabled')+'" id="wi-'+w.field+'" style="margin-bottom:10px;border-left:3px solid '+(ena?col:'rgba(255,255,255,0.06)')+'\">'
      +'<div class="weight-header">'
      +'<div class="weight-top">'
      +'<label class="toggle"><input type="checkbox" '+(ena?'checked':'')+' onchange="toggleWeight(\''+w.field+'\',this.checked)"><span class="toggle-track"></span></label>'
      +'<label class="field-label" style="margin:0">'+esc(w.label)+'</label></div>'
      +'<span class="weight-val mono accent" id="wv-'+w.field+'">'+w.weight.toFixed(1)+'</span>'
      +'<button class="weight-cfg-btn" onclick="toggleWeightConfig(\''+w.field+'\')" title="Advanced">&#9881;</button></div>'
      +'<div class="weight-config" id="wcfg-'+w.field+'" style="display:none">'
      +'<div class="wc-row">'
      +'<select class="wc-select" id="wd-'+w.field+'" onchange="onWeightDirection(\''+w.field+'\')">'
      +'<option value="lower" '+(dirLower?'selected':'')+'>'+t('direction_lower')+'</option>'
      +'<option value="higher" '+(!dirLower?'selected':'')+'>'+t('direction_higher')+'</option></select>'
      +'<select class="wc-select" id="wf-'+w.field+'" onchange="onWeightFormula(\''+w.field+'\')">'
      +'<option value="minmax" '+(!isDirect?'selected':'')+'>MinMax (category)</option>'
      +'<option value="direct" '+(isDirect?'selected':'')+'>Direct (fixed max)</option></select>'
      +'<input type="number" class="wc-max" id="wn-'+w.field+'" value="'+(w.formula_min!=null?w.formula_min:'')+'" placeholder="Min" step="0.01" oninput="onWeightMin(\''+w.field+'\')" style="'+(isDirect?'':'display:none')+'">'
      +'<input type="number" class="wc-max" id="wm-'+w.field+'" value="'+(w.formula_max!=null?w.formula_max:'')+'" placeholder="Max" step="0.01" oninput="onWeightMax(\''+w.field+'\')" style="'+(isDirect?'':'display:none')+'">'
      +'</div></div>'
      +'<input type="range" min="0" max="100" step="1" value="'+w.weight+'" id="w-'+w.field+'" class="weight-slider" oninput="onWeightSlider(\''+w.field+'\')">'
      +'</div>';
  });
  container.innerHTML=h;
  renderWeightBar();
}

function toggleWeightConfig(field){
  var el=document.getElementById('wcfg-'+field);
  if(el) el.style.display=el.style.display==='none'?'':'none';
}

function toggleWeight(field,checked){
  var item=weightData.find(function(w){return w.field===field;});
  if(item)item.enabled=checked;
  var el=document.getElementById('wi-'+field);
  var col=SCORE_COLORS[field]||'#888';
  if(el){el.className='weight-item '+(checked?'enabled':'disabled');el.style.borderLeftColor=checked?col:'rgba(255,255,255,0.06)';}
  renderWeightBar();
}


function onWeightDirection(field){
  var item=weightData.find(function(w){return w.field===field;});
  if(item)item.direction=document.getElementById('wd-'+field).value;
}

function onWeightFormula(field){
  var item=weightData.find(function(w){return w.field===field;});
  var val=document.getElementById('wf-'+field).value;
  if(item)item.formula=val;
  var minEl=document.getElementById('wn-'+field);
  var maxEl=document.getElementById('wm-'+field);
  if(minEl)minEl.style.display=val==='direct'?'':'none';
  if(maxEl)maxEl.style.display=val==='direct'?'':'none';
}

function onWeightMin(field){
  var item=weightData.find(function(w){return w.field===field;});
  if(item){
    item.formula_min=parseFloat(document.getElementById('wn-'+field).value)||0;
  }
}

function onWeightMax(field){
  var item=weightData.find(function(w){return w.field===field;});
  if(item){
    item.formula_max=parseFloat(document.getElementById('wm-'+field).value)||0;
  }
}

function onWeightSlider(field){
  var val=parseFloat(document.getElementById('w-'+field).value);
  document.getElementById('wv-'+field).textContent=val.toFixed(1);
  var item=weightData.find(function(w){return w.field===field;});
  if(item)item.weight=val;
  renderWeightBar();
}

function renderWeightBar(){
  var enabled=weightData.filter(function(w){return w.enabled;});
  var total=enabled.reduce(function(s,w){return s+w.weight;},0);
  var wrap=document.getElementById('weight-bar-wrap');
  var h='<div class="weight-bar-title">Distribution ('+enabled.length+' active)</div><div class="weight-bar-track">';
  enabled.forEach(function(w){
    var pct=total>0?(w.weight/total*100):0;
    var col=SCORE_COLORS[w.field]||'#888';
    h+='<div class="weight-bar-seg" style="width:'+pct+'%;background:'+col+'" title="'+esc(w.label)+': '+pct.toFixed(0)+'%"></div>';
  });
  if(!enabled.length)h+='<div style="width:100%;text-align:center;font-size:11px;color:rgba(255,255,255,0.2);line-height:24px">None active</div>';
  h+='</div><div class="weight-bar-legend">';
  enabled.forEach(function(w){
    var pct=total>0?(w.weight/total*100):0;
    var col=SCORE_COLORS[w.field]||'#888';
    h+='<span class="weight-bar-legend-item"><span class="weight-bar-dot" style="background:'+col+'"></span>'+esc(w.label)+' '+pct.toFixed(0)+'%</span>';
  });
  h+='</div>';wrap.innerHTML=h;
}

async function saveWeights(){
  var btn=document.getElementById('btn-save-weights');btn.disabled=true;btn.textContent=t('toast_saving');
  try{
    var payload=weightData.map(function(w){
      var minEl=document.getElementById('wn-'+w.field);
      var maxEl=document.getElementById('wm-'+w.field);
      var sliderEl=document.getElementById('w-'+w.field);
      var obj={field:w.field,enabled:w.enabled,weight:parseFloat(sliderEl?sliderEl.value:w.weight),direction:w.direction,formula:w.formula,formula_min:parseFloat(minEl?minEl.value:0)||0,formula_max:parseFloat(maxEl?maxEl.value:0)||0};
      return obj;
    });
    console.log('saveWeights payload:',JSON.stringify(payload));
    var resp=await api('/api/weights',{method:'PUT',body:JSON.stringify(payload)});
    console.log('saveWeights response:',JSON.stringify(resp));
    showToast(t('toast_weights_saved'),'success');
    loadData();
  }catch(e){console.error('saveWeights error:',e);showToast(t('toast_save_error'),'error');}
  btn.disabled=false;btn.textContent=t('btn_save_weights');
}

async function resetWeights(){
  if(!confirm('Reset to default values?'))return;
  var defaults={
    kcal:{e:1,w:38.18,d:'lower',f:'minmax',mn:0,mx:0},
    carbs:{e:1,w:5.09,d:'lower',f:'minmax',mn:0,mx:0},
    protein:{e:1,w:40,d:'higher',f:'minmax',mn:0,mx:0},
    taste_score:{e:1,w:31.82,d:'higher',f:'direct',mn:0,mx:6},
    volume:{e:1,w:44.09,d:'higher',f:'minmax',mn:0,mx:0},
    price:{e:1,w:44.09,d:'lower',f:'minmax',mn:0,mx:0}
  };
  var cfgDefaults={
    kcal:{d:'lower',f:'minmax',mn:0,mx:0},energy_kj:{d:'lower',f:'minmax',mn:0,mx:0},
    carbs:{d:'lower',f:'minmax',mn:0,mx:0},sugar:{d:'lower',f:'minmax',mn:0,mx:0},
    fat:{d:'lower',f:'minmax',mn:0,mx:0},saturated_fat:{d:'lower',f:'minmax',mn:0,mx:0},
    protein:{d:'higher',f:'minmax',mn:0,mx:0},fiber:{d:'higher',f:'minmax',mn:0,mx:0},
    salt:{d:'lower',f:'minmax',mn:0,mx:0},taste_score:{d:'higher',f:'direct',mn:0,mx:6},
    volume:{d:'higher',f:'minmax',mn:0,mx:0},price:{d:'lower',f:'minmax',mn:0,mx:0}
  };
  weightData.forEach(function(item){
    var d=defaults[item.field];
    var c=cfgDefaults[item.field]||{d:'lower',f:'minmax',m:0};
    item.enabled=d?true:false;
    item.weight=d?d.w:0;
    item.direction=d?d.d:c.d;
    item.formula=d?d.f:c.f;
    item.formula_min=d?d.mn:c.mn;
    item.formula_max=d?d.mx:c.mx;
  });
  renderWeightItems();
  await saveWeights();
}

// ── Categories ──────────────────────────────────────
async function loadCategories(){
  var cats=await api('/api/categories');var list=document.getElementById('cat-list');
  if(!cats.length){list.innerHTML='<p style="color:rgba(255,255,255,0.3);font-size:13px">No categories</p>';return;}
  var h='';cats.forEach(function(c){var canDel=c.count===0;
    h+='<div class="cat-item"><span class="cat-item-emoji">'+esc(c.emoji)+'</span>'
      +'<input class="cat-item-label-input" value="'+esc(c.label)+'" onchange="updateCategoryLabel(\''+esc(c.name).replace(/'/g,"\\'")+'\',this.value)" title="'+ t('label_display_name')+'">'
      +'<span class="cat-item-key">'+esc(c.name)+'</span><span class="cat-item-count">'+c.count+' prod.</span>'
      +'<button class="btn-sm btn-red" '+(canDel?'':'disabled')+' onclick="deleteCategory(\''+esc(c.name).replace(/'/g,"\\'")+'\',\''+esc(c.label).replace(/'/g,"\\'")+'\')">&#128465;</button></div>';
  });list.innerHTML=h;
}
async function updateCategoryLabel(name,val){if(!val.trim()){showToast(t('toast_display_name_empty'),'error');loadCategories();return;}await api('/api/categories/'+encodeURIComponent(name),{method:'PUT',body:JSON.stringify({label:val.trim()})});showToast(t('toast_category_updated'),'success');await fetchStats();}
async function addCategory(){var name=document.getElementById('cat-name').value.trim(),emoji=document.getElementById('cat-emoji').value.trim()||'\u{1F4E6}',label=document.getElementById('cat-label').value.trim();if(!name||!label){showToast(t('toast_name_display_required'),'error');return;}var res=await api('/api/categories',{method:'POST',body:JSON.stringify({name:name,emoji:emoji,label:label})});if(res.error){showToast(res.error,'error');return;}document.getElementById('cat-name').value='';document.getElementById('cat-emoji').value='';document.getElementById('cat-label').value='';showToast(t('toast_category_added',{name:label}),'success');await fetchStats();loadCategories();}
async function deleteCategory(name,label){if(!confirm(t('confirm_delete_category',{name:label})))return;var res=await api('/api/categories/'+encodeURIComponent(name),{method:'DELETE'});if(res.error){showToast(res.error,'error');return;}showToast(t('toast_category_deleted',{name:label}),'success');await fetchStats();loadCategories();}

// ── Protein Quality Settings ──────────────────────────
var pqData=[];
var pqEditingId=null;


async function loadPq(){
  try{pqData=await api('/api/protein-quality');}catch(e){pqData=[];}
  renderPqTable();
}

function renderPqTable(){
  var container=document.getElementById('pq-list');
  if(!pqData.length){container.innerHTML='<p style="color:rgba(255,255,255,0.3);font-size:13px;text-align:center;padding:20px">No protein sources</p>';return;}
  var h='';
  pqData.forEach(function(row){
    if(pqEditingId===row.id){
      h+='<div class="pq-card">'
        +'<div class="pq-card-edit">'
        +'<div><label class="field-label">Name</label><input class="pq-edit-input" id="pqe-label-'+row.id+'" value="'+esc(row.label)+'"></div>'
        +'<div><label class="field-label">Keywords</label><input class="pq-edit-input" id="pqe-kw-'+row.id+'" value="'+esc(row.keywords.join(', '))+'"></div>'
        +'<div class="pq-edit-row-fields">'
        +'<div><label class="field-label">PDCAAS</label><input class="pq-edit-input mono" id="pqe-pdcaas-'+row.id+'" type="number" step="0.01" min="0" max="1" value="'+row.pdcaas+'"></div>'
        +'<div><label class="field-label">DIAAS</label><input class="pq-edit-input mono" id="pqe-diaas-'+row.id+'" type="number" step="0.01" min="0" max="1.2" value="'+row.diaas+'"></div>'
        +'</div>'
        +'<div class="pq-edit-btns"><button class="pq-btn pq-btn-save" onclick="savePqEdit('+row.id+')">&#10003; Save</button><button class="pq-btn pq-btn-cancel" onclick="cancelPqEdit()">&#10005; Cancel</button></div>'
        +'</div></div>';
    } else {
      h+='<div class="pq-card">'
        +'<div class="pq-card-top">'
        +'<span class="pq-label">'+esc(row.label||row.keywords[0])+'</span>'
        +'<span class="pq-badges"><span class="pq-badge"><span class="pq-badge-label">P </span>'+row.pdcaas.toFixed(2)+'</span><span class="pq-badge"><span class="pq-badge-label">D </span>'+row.diaas.toFixed(2)+'</span></span>'
        +'<div class="pq-card-actions"><button class="pq-btn pq-btn-edit" onclick="startPqEdit('+row.id+')">&#9998;</button><button class="pq-btn pq-btn-del" onclick="deletePq('+row.id+',\''+esc(row.label||row.keywords[0]).replace(/'/g,"\\'")+'\')">&#128465;</button></div>'
        +'</div>'
        +'<div class="pq-kw">'+esc(row.keywords.join(', '))+'</div>'
        +'</div>';
    }
  });
  container.innerHTML=h;
}

function startPqEdit(id){pqEditingId=id;renderPqTable();}
function cancelPqEdit(){pqEditingId=null;renderPqTable();}

async function savePqEdit(id){
  var label=document.getElementById('pqe-label-'+id).value.trim();
  var kw=document.getElementById('pqe-kw-'+id).value.trim();
  var pdcaas=parseFloat(document.getElementById('pqe-pdcaas-'+id).value);
  var diaas=parseFloat(document.getElementById('pqe-diaas-'+id).value);
  if(!kw||isNaN(pdcaas)||isNaN(diaas)){showToast(t('toast_fill_all_fields'),'error');return;}
  var keywords=kw.split(',').map(function(k){return k.trim();}).filter(Boolean);
  var res=await api('/api/protein-quality/'+id,{method:'PUT',body:JSON.stringify({label:label,keywords:keywords,pdcaas:pdcaas,diaas:diaas})});
  if(res.error){showToast(res.error,'error');return;}
  pqEditingId=null;
  showToast(t('toast_updated'),'success');
  loadPq();
}

async function addPq(){
  var label=document.getElementById('pq-add-label').value.trim();
  var kw=document.getElementById('pq-add-kw').value.trim();
  var pdcaas=parseFloat(document.getElementById('pq-add-pdcaas').value);
  var diaas=parseFloat(document.getElementById('pq-add-diaas').value);
  if(!kw||isNaN(pdcaas)||isNaN(diaas)){showToast(t('toast_pq_keywords_required'),'error');return;}
  var keywords=kw.split(',').map(function(k){return k.trim();}).filter(Boolean);
  var res=await api('/api/protein-quality',{method:'POST',body:JSON.stringify({label:label,keywords:keywords,pdcaas:pdcaas,diaas:diaas})});
  if(res.error){showToast(res.error,'error');return;}
  document.getElementById('pq-add-label').value='';document.getElementById('pq-add-kw').value='';
  document.getElementById('pq-add-pdcaas').value='';document.getElementById('pq-add-diaas').value='';
  showToast(t('toast_pq_added',{name:(label||keywords[0])}),'success');
  loadPq();
}

async function deletePq(id,label){
  if(!confirm(t('confirm_delete_product',{name:label})))return;
  await api('/api/protein-quality/'+id,{method:'DELETE'});
  showToast(t('toast_pq_deleted',{name:label}),'success');
  loadPq();
}

// ── Backup / Restore / Import ───────────────────────
function downloadBackup(){window.location.href='/api/backup';showToast(t('toast_backup_downloaded'),'success');}

function handleRestore(input){
  if(!input.files.length)return;
  if(!confirm('Are you sure? This replaces ALL existing data in the database.')){input.value='';return;}
  var reader=new FileReader();
  reader.onload=async function(e){
    try{var data=JSON.parse(e.target.result);var res=await api('/api/restore',{method:'POST',body:JSON.stringify(data)});if(res.error){showToast(res.error,'error');}else{imageCache={};showToast(res.message,'success');loadData();if(currentView==='settings')loadSettings();}}catch(err){showToast(t('toast_invalid_file'),'error');}
    input.value='';};reader.readAsText(input.files[0]);
}
function handleImport(input){
  if(!input.files.length)return;
  var reader=new FileReader();
  reader.onload=async function(e){
    try{var data=JSON.parse(e.target.result);var res=await api('/api/import',{method:'POST',body:JSON.stringify(data)});if(res.error){showToast(res.error,'error');}else{imageCache={};showToast(res.message,'success');loadData();if(currentView==='settings')loadSettings();}}catch(err){showToast(t('toast_invalid_file'),'error');}
    input.value='';};reader.readAsText(input.files[0]);
}

(function(){
  var drop=document.getElementById('restore-drop');
  drop.addEventListener('dragover',function(e){e.preventDefault();drop.classList.add('dragover');});
  drop.addEventListener('dragleave',function(){drop.classList.remove('dragover');});
  drop.addEventListener('drop',function(e){e.preventDefault();drop.classList.remove('dragover');if(e.dataTransfer.files.length){var fi={files:e.dataTransfer.files};Object.defineProperty(fi,'value',{set:function(){},get:function(){return'';}});handleRestore(fi);}});
})();

// ── Barcode Scanner ─────────────────────────────────
var _scanner=null;
var _scannerCtx={prefix:null,productId:null};

function openScanner(prefix,productId){
  _scannerCtx={prefix:prefix,productId:productId||null};

  if(typeof Html5Qrcode==='undefined'){
    showToast(t('toast_scanner_load_error'),'error');
    return;
  }

  // Create scanner UI
  var bg=document.createElement('div');bg.className='scanner-bg';bg.id='scanner-bg';
  document.body.style.overflow='hidden';
  bg.innerHTML='<div class="scanner-header"><h3>\u{1F4F7} Scan barcode</h3><button class="scanner-close" onclick="closeScanner()">&times;</button></div>'
    +'<div class="scanner-video-wrap"><div id="scanner-reader"></div>'
    +'<div class="scanner-hint">Hold the barcode within the frame</div></div>';
  document.body.appendChild(bg);

  // Start scanner
  _scanner=new Html5Qrcode('scanner-reader');
  _scanner.start(
    {facingMode:'environment'},
    {fps:15,qrbox:function(vw,vh){
      var w=Math.min(vw*0.8,300);
      return {width:Math.round(w),height:Math.round(w*0.45)};
    },
    formatsToSupport:[
      Html5QrcodeSupportedFormats.EAN_13,
      Html5QrcodeSupportedFormats.EAN_8,
      Html5QrcodeSupportedFormats.UPC_A,
      Html5QrcodeSupportedFormats.UPC_E
    ]},
    function onSuccess(code){
      onBarcodeDetected(code);
    },
    function onError(){}
  ).catch(function(err){
    console.error('Scanner start error:',err);
    var wrap=document.querySelector('.scanner-video-wrap');
    if(wrap)wrap.innerHTML='<div class="scanner-error"><div class="scanner-error-icon">\u{1F4F7}</div><p>Could not open the camera. Check that you have granted camera permission.</p><button class="btn-sm btn-outline" style="margin-top:16px" onclick="closeScanner()">Close</button></div>';
  });
}

function onBarcodeDetected(code){
  if(navigator.vibrate)navigator.vibrate(100);

  var prefix=_scannerCtx.prefix;
  var productId=_scannerCtx.productId;
  var eanEl=document.getElementById(prefix+'-ean');
  if(eanEl)eanEl.value=code;
  validateOffBtn(prefix);

  closeScanner();

  showToast(t('toast_barcode_scanned',{code:code}),'success');
  setTimeout(function(){
    lookupOFF(prefix,productId);
  },300);
}

function closeScanner(){
  if(_scanner){_scanner.stop().then(function(){_scanner.clear();}).catch(function(){});_scanner=null;}
  var el=document.getElementById('scanner-bg');if(el)el.remove();
  document.body.style.overflow='';
}

// ── Search Scanner (scan to find product in DB) ─────
var _searchScanMode=false;

function openSearchScanner(){
  _searchScanMode=true;
  _scannerCtx={prefix:'search',productId:null};

  if(typeof Html5Qrcode==='undefined'){
    showToast(t('toast_scanner_not_loaded'),'error');
    return;
  }

  var bg=document.createElement('div');bg.className='scanner-bg';bg.id='scanner-bg';
  document.body.style.overflow='hidden';
  bg.innerHTML='<div class="scanner-header"><h3>\u{1F50D} Scan to find product</h3><button class="scanner-close" onclick="closeScanner();_searchScanMode=false;">&times;</button></div>'
    +'<div class="scanner-video-wrap"><div id="scanner-reader"></div>'
    +'<div class="scanner-hint">Scan the barcode on the product</div></div>';
  document.body.appendChild(bg);

  _scanner=new Html5Qrcode('scanner-reader');
  _scanner.start(
    {facingMode:'environment'},
    {fps:15,qrbox:function(vw,vh){
      var w=Math.min(vw*0.8,300);
      return {width:Math.round(w),height:Math.round(w*0.45)};
    },
    formatsToSupport:[
      Html5QrcodeSupportedFormats.EAN_13,
      Html5QrcodeSupportedFormats.EAN_8,
      Html5QrcodeSupportedFormats.UPC_A,
      Html5QrcodeSupportedFormats.UPC_E
    ]},
    function onSuccess(code){
      if(_searchScanMode){
        _searchScanMode=false;
        onSearchScanDetected(code);
      }
    },
    function onError(){}
  ).catch(function(err){
    console.error('Scanner start error:',err);
    var wrap=document.querySelector('.scanner-video-wrap');
    if(wrap)wrap.innerHTML='<div class="scanner-error"><div class="scanner-error-icon">\u{1F4F7}</div><p>Could not open the camera. Check that you have granted camera permission.</p><button class="btn-sm btn-outline" style="margin-top:16px" onclick="closeScanner();_searchScanMode=false;">Close</button></div>';
  });
}

async function onSearchScanDetected(code){
  if(navigator.vibrate)navigator.vibrate(100);
  closeScanner();
  showToast(t('toast_barcode_scanned',{code:code}),'success');

  // Ensure we're on search view
  if(currentView!=='search')switchView('search');

  // Fetch ALL products to search across all categories
  var allProducts=await fetchProducts('',[]); 

  // Find product by EAN
  var found=null;
  for(var i=0;i<allProducts.length;i++){
    if(allProducts[i].ean===code){found=allProducts[i];break;}
  }

  if(found){
    // Filter to the product's category
    currentFilter=[found.type];
    buildFilters();

    // Sort by total_score descending
    sortCol='total_score';
    sortDir='desc';

    // Fetch filtered products and render
    var filtered=await fetchProducts('',currentFilter);
    renderResults(filtered,'');

    // Clear search input
    document.getElementById('search-input').value='';
    document.getElementById('search-clear').classList.remove('visible');

    // Open filters to show category selection
    var filterRow=document.getElementById('filter-row');
    var filterTog=document.getElementById('filter-toggle');
    if(!filterRow.classList.contains('open')){filterRow.classList.add('open');filterTog.classList.add('open');}

    // Scroll to the product and highlight it
    setTimeout(function(){
      var rowEl=document.querySelector('.table-row[onclick="toggleExpand('+found.id+')"]');
      if(rowEl){
        rowEl.classList.add('scan-highlight');
        rowEl.scrollIntoView({behavior:'smooth',block:'center'});
        // Remove highlight after animation
        setTimeout(function(){rowEl.classList.remove('scan-highlight');},5000);
      }
    },150);
  } else {
    // Product not found — show modal
    showScanNotFoundModal(code);
  }
}

function showScanNotFoundModal(ean){
  var bg=document.createElement('div');bg.className='scan-modal-bg';bg.id='scan-modal-bg';
  bg.onclick=function(e){if(e.target===bg)closeScanModal();};
  bg.innerHTML='<div class="scan-modal">'
    +'<div class="scan-modal-icon">\u{1F50D}</div>'
    +'<h3>Product not found</h3>'
    +'<div class="scan-modal-ean">EAN: '+ean+'</div>'
    +'<p>This barcode is not in the database. What would you like to do?</p>'
    +'<div class="scan-modal-actions">'
    +'<button class="scan-modal-btn-register" onclick="scanRegisterNew(\''+ean+'\')">+ Register new product</button>'
    +'<button class="scan-modal-btn-update" onclick="scanUpdateExisting(\''+ean+'\')">\u270E Update existing product</button>'
    +'<button class="scan-modal-btn-cancel" onclick="closeScanModal()">Cancel</button>'
    +'</div></div>';
  document.body.appendChild(bg);
  document.body.style.overflow='hidden';
}

function closeScanModal(){
  var el=document.getElementById('scan-modal-bg');if(el)el.remove();
  document.body.style.overflow='';
}

function scanRegisterNew(ean){
  closeScanModal();
  switchView('register');
  // Pre-fill EAN and trigger OFF lookup
  var eanEl=document.getElementById('f-ean');
  if(eanEl)eanEl.value=ean;
  validateOffBtn('f');
  setTimeout(function(){lookupOFF('f');},300);
}

function scanUpdateExisting(ean){
  closeScanModal();
  showScanProductPicker(ean);
}

// ── Scan Product Picker: search local DB to assign EAN ──
var _scanPickerEan=null;

function showScanProductPicker(ean){
  _scanPickerEan=ean;
  document.body.style.overflow='hidden';
  var bg=document.createElement('div');bg.className='off-modal-bg';bg.id='scan-picker-bg';
  bg.onclick=function(e){if(e.target===bg)closeScanPicker();};
  bg.innerHTML='<div class="off-modal"><div class="off-modal-head"><h3>\u270E '+t('off_search_btn')+' — EAN '+ean+'</h3><button class="off-modal-close" onclick="closeScanPicker()">&times;</button></div>'
    +'<div class="off-modal-search"><input id="scan-picker-input" placeholder="'+t('search_placeholder')+'" onkeydown="if(event.key===\'Enter\')scanPickerSearch()"><button onclick="scanPickerSearch()">'+t('off_search_btn')+'</button></div>'
    +'<div class="off-modal-count" id="scan-picker-count">'+t('search_placeholder')+'</div>'
    +'<div class="off-modal-body" id="scan-picker-body"><div class="off-modal-empty">\u{1F50D} '+t('search_placeholder')+'</div></div></div>';
  document.body.appendChild(bg);
  setTimeout(function(){var inp=document.getElementById('scan-picker-input');if(inp)inp.focus();},100);
}

function closeScanPicker(){
  var el=document.getElementById('scan-picker-bg');if(el)el.remove();
  document.body.style.overflow='';
  _scanPickerEan=null;
}

async function scanPickerSearch(){
  var inp=document.getElementById('scan-picker-input');
  var query=inp?inp.value.trim():'';
  if(!query){showToast(t('toast_enter_product_name'),'error');return;}
  var body=document.getElementById('scan-picker-body');
  var cnt=document.getElementById('scan-picker-count');
  body.innerHTML='<div style="display:flex;align-items:center;justify-content:center;padding:40px 0"><span class="spinner"></span></div>';
  if(cnt)cnt.textContent='Searching for "'+query+'"...';
  try{
    var results=await fetchProducts(query,[]);
    if(!results.length){
      body.innerHTML='<div class="off-modal-empty">No products found for "'+esc(query)+'"</div>';
      if(cnt)cnt.textContent=t('off_zero_results');
      return;
    }
    if(cnt)cnt.textContent=results.length+' resultat'+(results.length!==1?'er':'');
    var h='';
    results.forEach(function(p,idx){
      var imgTag=p.has_image?'<div class="off-result-img" id="scan-pick-img-'+p.id+'" style="background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center"><span style="opacity:0.2">'+catEmoji(p.type)+'</span></div>'
        :'<div class="off-result-img" style="display:flex;align-items:center;justify-content:center"><span style="font-size:20px">'+catEmoji(p.type)+'</span></div>';
      var eanInfo=p.ean?'<span class="off-result-ean">EAN: '+esc(p.ean)+'</span>':'<span class="off-result-ean" style="color:rgba(255,100,100,0.5)">No EAN</span>';
      h+='<div class="off-result" onclick="scanPickerSelect('+p.id+')">'
        +imgTag
        +'<div class="off-result-info"><div class="off-result-name">'+esc(p.name)+'</div>'
        +'<div class="off-result-brand">'+catLabel(p.type)+(p.brand?' \u00B7 '+esc(p.brand):'')+'</div>'
        +eanInfo+'</div></div>';
    });
    body.innerHTML=h;
    // Load thumbnails
    results.forEach(function(p){
      if(p.has_image){
        loadProductImage(p.id).then(function(dataUri){
          if(!dataUri)return;
          var el=document.getElementById('scan-pick-img-'+p.id);
          if(el){var safe=safeDataUri(dataUri);if(safe)el.innerHTML='<img src="'+safe+'" style="width:100%;height:100%;object-fit:cover;border-radius:8px">';}
        });
      }
    });
  }catch(e){
    body.innerHTML='<div class="off-modal-empty">'+t('toast_save_error')+'</div>';
    if(cnt)cnt.textContent=t('toast_save_error');
  }
}

async function scanPickerSelect(productId){
  var ean=_scanPickerEan;
  if(!ean)return;
  closeScanPicker();

  // Save EAN to the selected product
  showToast(t('toast_saving_ean',{ean:ean}),'info');
  try{
    // Fetch current product data, update EAN
    var prod=await api('/api/products/'+productId);
    prod.ean=ean;
    await api('/api/products/'+productId,{method:'PUT',body:JSON.stringify(prod)});
    showToast(t('toast_ean_saved',{name:prod.name}),'success');
  }catch(e){
    showToast(t('toast_ean_save_error'),'error');
    return;
  }

  // Ask if user wants to fetch OFF data
  showScanOffConfirm(ean,productId);
}

function showScanOffConfirm(ean,productId){
  document.body.style.overflow='hidden';
  var bg=document.createElement('div');bg.className='scan-modal-bg';bg.id='scan-off-confirm-bg';
  bg.onclick=function(e){if(e.target===bg)closeScanOffConfirm();};
  bg.innerHTML='<div class="scan-modal">'
    +'<div class="scan-modal-icon">\u{1F30E}</div>'
    +'<h3>Fetch data from OpenFoodFacts?</h3>'
    +'<div class="scan-modal-ean">EAN: '+ean+'</div>'
    +'<p>Look up nutrition and product info from OpenFoodFacts for this barcode?</p>'
    +'<div class="scan-modal-actions">'
    +'<button class="scan-modal-btn-register" onclick="scanOffFetch(\''+ean+'\','+productId+')">\u{1F30E} Yes, fetch data</button>'
    +'<button class="scan-modal-btn-cancel" onclick="closeScanOffConfirm();loadData();">No, skip</button>'
    +'</div></div>';
  document.body.appendChild(bg);
}

function closeScanOffConfirm(){
  var el=document.getElementById('scan-off-confirm-bg');if(el)el.remove();
  document.body.style.overflow='';
}

async function scanOffFetch(ean,productId){
  closeScanOffConfirm();
  // Expand the product in the table so it enters edit mode with ed- prefixed fields
  if(currentView!=='search')switchView('search');
  currentFilter=[];
  buildFilters();
  await loadData();
  // Expand + enter edit mode for the product
  expandedId=productId;
  editingId=productId;
  rerender();
  // Wait for DOM, then trigger OFF lookup on the edit form
  setTimeout(function(){
    var eanEl=document.getElementById('ed-ean');
    if(eanEl)eanEl.value=ean;
    validateOffBtn('ed');
    setTimeout(function(){lookupOFF('ed',productId);},200);
  },300);
}

// ── OpenFoodFacts Lookup ────────────────────────────
function isValidEan(v){if(!v)return false;var s=v.replace(/\s/g,'');return /^\d{8,13}$/.test(s);}
function validateOffBtn(prefix){
  var ean=document.getElementById(prefix+'-ean').value.trim();
  var name=document.getElementById(prefix+'-name').value.trim();
  var btn=document.getElementById(prefix+'-off-btn');
  if(btn)btn.disabled=!(isValidEan(ean)||name.length>=2);
}

// Pending context for modal callback
var _offCtx={prefix:null,productId:null};

async function lookupOFF(prefix,productId){
  var ean=document.getElementById(prefix+'-ean').value.replace(/\s/g,'');
  var name=document.getElementById(prefix+'-name').value.trim();
  _offCtx={prefix:prefix,productId:productId||null};

  if(isValidEan(ean)){
    // Direct EAN lookup — open modal with spinner
    showOffPickerLoading(t('off_searching_ean',{ean:ean}));
    try{
      var res=await fetch('https://world.openfoodfacts.org/api/v2/product/'+ean+'.json');
      var data=await res.json();
      if(data.status!==1||!data.product){
        updateOffPickerResults([],t('no_products_found')+' (EAN '+ean+')');
        return;
      }
      await applyOffProduct(data.product,prefix,productId);
      closeOffPicker();
    }catch(e){console.error('OFF lookup error:',e);updateOffPickerResults([],'Kunne ikke kontakte OpenFoodFacts');}
  } else if(name.length>=2){
    // Name search — open modal with spinner then populate
    showOffPickerLoading(t('off_searching_name',{name:name}));
    try{
      var products=await searchOFF(name);
      updateOffPickerResults(products);
      var si=document.getElementById('off-search-input');
      if(si)si.value=name;
    }catch(e){console.error('OFF search error:',e);updateOffPickerResults([],'Kunne ikke kontakte OpenFoodFacts');}
  }
}

function showOffPickerLoading(msg){
  closeOffPicker();
  document.body.style.overflow='hidden';
  var bg=document.createElement('div');bg.className='off-modal-bg';bg.id='off-modal-bg';
  bg.onclick=function(e){if(e.target===bg)closeOffPicker();};
  var h='<div class="off-modal"><div class="off-modal-head"><h3>&#127758; OpenFoodFacts</h3><button class="off-modal-close" onclick="closeOffPicker()">&times;</button></div>'
    +'<div class="off-modal-search"><input id="off-search-input" placeholder="Search OpenFoodFacts..." disabled onkeydown="if(event.key===\'Enter\')offModalSearch()"><button id="off-search-btn" disabled onclick="offModalSearch()">Search</button></div>'
    +'<div class="off-modal-count" id="off-result-count">'+(msg||t('off_searching'))+'</div>'
    +'<div class="off-modal-body" id="off-results-body"><div style="display:flex;align-items:center;justify-content:center;padding:40px 0"><span class="spinner"></span></div></div></div>';
  bg.innerHTML=h;
  document.body.appendChild(bg);
}

function updateOffPickerResults(products,errorMsg){
  var body=document.getElementById('off-results-body');
  var count=document.getElementById('off-result-count');
  var si=document.getElementById('off-search-input');
  var sb=document.getElementById('off-search-btn');
  if(si){si.disabled=false;}
  if(sb){sb.disabled=false;sb.textContent=t('off_search_btn');}
  if(!body)return;
  if(errorMsg){
    body.innerHTML='<div class="off-modal-empty">'+esc(errorMsg)+'</div>';
    if(count)count.textContent=t('off_zero_results');
    return;
  }
  window._offPickerProducts=products;
  body.innerHTML=renderOffResults(products);
  if(count)count.textContent=t('off_result_count',{count:products.length});
}

async function searchOFF(query){
  var q=encodeURIComponent(query);
  var url='https://world.openfoodfacts.org/cgi/search.pl?search_terms='+q+'&search_simple=1&action=process&json=1&page_size=20&fields=code,product_name,product_name_no,brands,stores,stores_tags,nutriments,image_front_small_url,image_front_url,image_url,serving_size,product_quantity,ingredients_text,ingredients_text_no,ingredients_text_en';
  var res=await fetch(url);
  var data=await res.json();
  return (data.products||[]).filter(function(p){return p.product_name||p.product_name_no;});
}

function showOffPicker(products,query){
  // If modal already open, just update results
  var existing=document.getElementById('off-modal-bg');
  if(existing){
    updateOffPickerResults(products);
    var si=document.getElementById('off-search-input');
    if(si&&query)si.value=query;
    return;
  }
  showOffPickerLoading('');
  var si=document.getElementById('off-search-input');
  if(si&&query)si.value=query;
  updateOffPickerResults(products);
}

function renderOffResults(products){
  if(!products.length)return '<div class="off-modal-empty">No results. Try different search terms.</div>';
  var h='';
  products.forEach(function(p,i){
    var name=p.product_name_no||p.product_name||'Ukjent';
    var brand=p.brands||'';
    var img=p.image_front_small_url||'';
    var n=p.nutriments||{};
    var kcal=Math.round(n['energy-kcal_100g']||n['energy-kcal']||0);
    var pro=parseFloat(n['proteins_100g']||n['proteins']||0).toFixed(1);
    var carb=parseFloat(n['carbohydrates_100g']||n['carbohydrates']||0).toFixed(1);
    var code=p.code||'';
    h+='<div class="off-result" onclick="selectOffResult('+i+')">';
    if(img)h+='<img class="off-result-img" src="'+esc(img)+'" onerror="this.style.display=\'none\'">';
    else h+='<div class="off-result-img" style="display:flex;align-items:center;justify-content:center;font-size:20px;opacity:0.2">&#127828;</div>';
    h+='<div class="off-result-info"><div class="off-result-name">'+esc(name)+'</div>';
    if(brand)h+='<div class="off-result-brand">'+esc(brand)+'</div>';
    h+='<div class="off-result-nutri">'+kcal+' kcal \u00B7 '+pro+'g protein \u00B7 '+carb+'g carbs</div>';
    if(code)h+='<div class="off-result-ean">EAN: '+esc(code)+'</div>';
    h+='</div></div>';
  });
  return h;
}

async function offModalSearch(){
  var input=document.getElementById('off-search-input');
  var btn=document.getElementById('off-search-btn');
  var query=(input?input.value:'').trim();
  if(query.length<2)return;
  if(input){input.disabled=true;}
  if(btn){btn.disabled=true;btn.textContent='...';}
  var body=document.getElementById('off-results-body');
  var cnt=document.getElementById('off-result-count');
  if(body)body.innerHTML='<div style="display:flex;align-items:center;justify-content:center;padding:40px 0"><span class="spinner"></span></div>';
  if(cnt)cnt.textContent=t('off_searching_name',{name:query});
  try{
    var products=await searchOFF(query);
    updateOffPickerResults(products);
  }catch(e){updateOffPickerResults([],t('toast_save_error'));}
}

function closeOffPicker(){
  var el=document.getElementById('off-modal-bg');
  if(el)el.remove();
  document.body.style.overflow='';
  window._offPickerProducts=null;
}

async function selectOffResult(idx){
  var products=window._offPickerProducts;
  if(!products||!products[idx])return;
  var selected=products[idx];
  closeOffPicker();

  // If the selected product has a barcode, do a full lookup for complete data
  var code=selected.code;
  var prefix=_offCtx.prefix;
  var productId=_offCtx.productId;
  var btn=document.getElementById(prefix+'-off-btn');
  if(btn){btn.classList.add('loading');btn.disabled=true;}

  try{
    if(code){
      // Full lookup by EAN for complete nutriment data
      var res=await fetch('https://world.openfoodfacts.org/api/v2/product/'+code+'.json');
      var data=await res.json();
      if(data.status===1&&data.product){
        // Also fill in the EAN field
        var eanEl=document.getElementById(prefix+'-ean');
        if(eanEl)eanEl.value=code;
        await applyOffProduct(data.product,prefix,productId);
      } else {
        // Fallback: use the search result data directly
        await applyOffProduct(selected,prefix,productId);
      }
    } else {
      await applyOffProduct(selected,prefix,productId);
    }
  }catch(e){
    console.error('OFF select error:',e);
    await applyOffProduct(selected,prefix,productId);
  }

  if(btn){btn.classList.remove('loading');validateOffBtn(prefix);}
}

async function applyOffProduct(prod,prefix,productId){
  var n=prod.nutriments||{};
  var offMap={
    kcal: n['energy-kcal_100g']!=null?n['energy-kcal_100g']:n['energy-kcal']!=null?n['energy-kcal']:null,
    energy_kj: n['energy-kj_100g']!=null?n['energy-kj_100g']:n['energy-kj']!=null?n['energy-kj']:n['energy_100g']!=null?n['energy_100g']:null,
    fat: n['fat_100g']!=null?n['fat_100g']:n['fat']!=null?n['fat']:null,
    saturated_fat: n['saturated-fat_100g']!=null?n['saturated-fat_100g']:n['saturated-fat']!=null?n['saturated-fat']:null,
    carbs: n['carbohydrates_100g']!=null?n['carbohydrates_100g']:n['carbohydrates']!=null?n['carbohydrates']:null,
    sugar: n['sugars_100g']!=null?n['sugars_100g']:n['sugars']!=null?n['sugars']:null,
    protein: n['proteins_100g']!=null?n['proteins_100g']:n['proteins']!=null?n['proteins']:null,
    fiber: n['fiber_100g']!=null?n['fiber_100g']:n['fiber']!=null?n['fiber']:null,
    salt: n['salt_100g']!=null?n['salt_100g']:n['salt']!=null?n['salt']:null,
  };

  var filled=[];
  for(var key in offMap){
    var val=offMap[key];
    if(val==null)continue;
    var el=document.getElementById(prefix+'-'+key);
    if(el){
      el.value=(key==='kcal'||key==='energy_kj')?Math.round(val):parseFloat(val).toFixed(key==='salt'?2:1);
      filled.push(key);
    }
  }

  // Serving size → portion
  var serving=prod.serving_size||'';
  var servMatch=serving.match(/([\d.]+)\s*g/);
  if(servMatch){var el=document.getElementById(prefix+'-portion');if(el){el.value=Math.round(parseFloat(servMatch[1]));filled.push('portion');}}

  // Product weight → weight
  var qty=prod.product_quantity||0;
  if(qty){var el=document.getElementById(prefix+'-weight');if(el){el.value=Math.round(parseFloat(qty));filled.push('weight');}}

  // Fill product name (always overwrite)
  var nameEl=document.getElementById(prefix+'-name');
  if(nameEl){var pname=prod.product_name_no||prod.product_name||'';if(pname){nameEl.value=pname;filled.push('name');}}

  // Fill EAN if empty
  if(prod.code){
    var eanEl=document.getElementById(prefix+'-ean');
    if(eanEl&&!eanEl.value.trim()){eanEl.value=prod.code;filled.push('ean');}
  }

  // Brand
  var brand=prod.brands||'';
  if(brand){var brandEl=document.getElementById(prefix+'-brand');if(brandEl){brandEl.value=brand;filled.push('brand');}}

  // Stores
  var stores='';
  if(prod.stores)stores=prod.stores;
  else if(prod.stores_tags&&prod.stores_tags.length)stores=prod.stores_tags.map(function(s){return s.replace(/-/g,' ').replace(/\b\w/g,function(c){return c.toUpperCase();});}).join(', ');
  if(stores){var storesEl=document.getElementById(prefix+'-stores');if(storesEl){storesEl.value=stores;filled.push('stores');}}

  // Ingredients
  var ing=prod.ingredients_text_no||prod.ingredients_text_en||prod.ingredients_text||'';
  if(ing){var ingEl2=document.getElementById(prefix+'-ingredients');if(ingEl2){ingEl2.value=ing;filled.push('ingredients');updateEstimateBtn(prefix);}}

  // Handle image
  var imgUrl=prod.image_front_url||prod.image_url||prod.image_front_small_url||'';
  if(imgUrl){
    try{
      var imgDataUri=await fetchImageAsDataUri(imgUrl);
      if(imgDataUri){
        if(productId){
          await api('/api/products/'+productId+'/image',{method:'PUT',body:JSON.stringify({image:imgDataUri})});
          imageCache[productId]=imgDataUri;
          var imgEl=document.getElementById('prod-img-'+productId);
          if(imgEl)imgEl.src=imgDataUri;
          else{var wrap=document.getElementById('prod-img-wrap-'+productId);if(wrap){var safe=safeDataUri(imgDataUri);if(safe)wrap.innerHTML='<img id="prod-img-'+productId+'" src="'+safe+'" style="width:100%;height:100%;object-fit:cover">';}}
        } else {
          window._pendingImage=imgDataUri;
        }
        filled.push('image');
      }
    }catch(ie){console.log('Image fetch failed:',ie);}
  }

  showToast('Fetched from OFF: '+filled.join(', '),'success');
  // Auto-estimate protein quality if ingredients were filled
  if(ing){setTimeout(function(){estimateProteinQuality(prefix);},300);}
}

async function fetchImageAsDataUri(url){
  try{
    var r=await fetch(url);
    if(!r.ok)throw new Error('Not ok');
    var blob=await r.blob();
    return await blobToResizedDataUri(blob);
  }catch(e){
    try{
      var r3=await fetch('/api/proxy-image?url='+encodeURIComponent(url));
      if(!r3.ok)return null;
      var blob3=await r3.blob();
      return await blobToResizedDataUri(blob3);
    }catch(e3){return null;}
  }
}

function blobToResizedDataUri(blob){
  return new Promise(function(resolve){
    var reader=new FileReader();
    reader.onload=function(e){resizeImage(e.target.result,400).then(resolve);};
    reader.onerror=function(){resolve(null);};
    reader.readAsDataURL(blob);
  });
}

// ── Protein Quality Estimation ─────────────────────
function updateEstimateBtn(prefix){
  var ing=document.getElementById(prefix+'-ingredients');
  var wrap=document.getElementById(prefix+'-protein-quality-wrap');
  if(ing&&wrap)wrap.style.display=ing.value.trim()?'':'none';
}

async function estimateProteinQuality(prefix){
  var ingEl=document.getElementById(prefix+'-ingredients');
  var btn=document.getElementById(prefix+'-estimate-btn');
  var resultEl=document.getElementById(prefix+'-pq-result');
  var pdcaasEl=document.getElementById(prefix+'-pdcaas-val');
  var diEl=document.getElementById(prefix+'-diaas-val');
  var sourcesEl=document.getElementById(prefix+'-pq-sources');
  var hiddenPd=document.getElementById(prefix+'-est_pdcaas');
  var hiddenDi=document.getElementById(prefix+'-est_diaas');
  if(!ingEl||!ingEl.value.trim()){showToast('Ingredients missing','error');return;}
  if(btn){btn.classList.add('loading');btn.disabled=true;}
  try{
    var res=await fetch('/api/estimate-protein-quality',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ingredients:ingEl.value})
    });
    var data=await res.json();
    if(data.error){showToast(t('toast_error_prefix',{msg:data.error}),'error');return;}
    if(pdcaasEl)pdcaasEl.textContent=data.est_pdcaas.toFixed(2);
    if(diEl)diEl.textContent=data.est_diaas.toFixed(2);
    if(sourcesEl&&data.sources&&data.sources.length)sourcesEl.textContent=t('sources_label',{sources:data.sources.join(', ')});
    if(hiddenPd)hiddenPd.value=data.est_pdcaas!=null?data.est_pdcaas:'';
    if(hiddenDi)hiddenDi.value=data.est_diaas!=null?data.est_diaas:'';
    if(resultEl)resultEl.style.display='';
    if(!data.est_pdcaas&&!data.est_diaas)showToast(t('toast_no_protein_sources'),'error');
    else showToast(t('toast_protein_estimated'),'success');
  }catch(e){showToast(t('toast_network_error'),'error');}
  if(btn){btn.classList.remove('loading');btn.disabled=false;}
}

// ── Init ─────────────────────────────────────────────
(async function(){
  // Load language/translations first
  await initLanguage();
  // Load weight config so score breakdown labels are available
  try{
    var wc=await api('/api/weights');
    weightData=wc;
    wc.forEach(function(w){SCORE_CFG_MAP[w.field]={label:w.label,desc:w.desc,direction:w.direction};});
  }catch(e){}
  loadData();
  document.getElementById('search-input').focus();
})();
