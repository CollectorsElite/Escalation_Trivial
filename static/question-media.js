'use strict';

function imagePath(id) {
  return typeof id==='string' && /^[a-f0-9]{64}$/.test(id) ? '/api/question-images/'+id : '';
}

function imageFigure(src, alt, lazy=false) {
  if (!src) return '';
  return `<figure class="question-image"><img src="${esc(src)}" alt="${esc(alt || 'Illustrazione della domanda')}" ${lazy?'loading="lazy"':''}>
    <button type="button" class="image-enlarge" data-expand-image>${icon('full')}Ingrandisci immagine</button></figure>`;
}

function questionImage(q, lazy=false) {
  return imageFigure(imagePath(q?.image), q?.imageAlt, lazy);
}

function questionImageFields(q) {
  return `<fieldset class="image-editor"><legend>Immagine della domanda</legend>
    <div data-editor-image></div>
    <label>Carica o sostituisci l’immagine<input type="file" name="imageFile" accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp" aria-describedby="image-limits"></label>
    <small id="image-limits" class="edit-hint">Facoltativa. JPG, PNG o WebP fino a 5 MB e 24 megapixel.</small>
    <p data-image-feedback class="form-error" role="alert" hidden></p>
    <button type="button" class="btn text-btn" data-remove-image>Rimuovi immagine</button>
    <label data-image-description>Descrizione per chi usa un lettore di schermo<textarea name="imageAlt" maxlength="600" rows="2" placeholder="Descrivi ciò che serve per rispondere, senza anticipare la soluzione.">${esc(q?.imageAlt)}</textarea></label>
  </fieldset>`;
}

function bindQuestionImageEditor(form, q, refreshPhone) {
  const input=form.elements.imageFile, alt=form.elements.imageAlt;
  const holder=$('[data-editor-image]',form), remove=$('[data-remove-image]',form);
  const description=$('[data-image-description]',form), feedback=$('[data-image-feedback]',form);
  let saved=q?.image || null, file=null, localURL='';
  const source=()=>localURL || imagePath(saved);
  function release() {
    if (localURL) URL.revokeObjectURL(localURL);
    localURL='';
  }
  function cleanOnClose() {
    if (form.isConnected && dlg.open) return;
    release();
    dlg.removeEventListener('close',cleanOnClose);
  }
  dlg.addEventListener('close',cleanOnClose);
  function display() {
    holder.innerHTML=imageFigure(source(),alt.value);
    description.hidden=!source();
    remove.hidden=!source() && feedback.hidden;
  }
  input.onchange=()=>{
    const chosen=input.files?.[0];
    if (!chosen) return;
    const validType=chosen.type ? ['image/png','image/jpeg','image/webp'].includes(chosen.type) : /\.(?:png|jpe?g|webp)$/i.test(chosen.name);
    const error=!validType ? 'Scegli un file JPG, PNG o WebP.' : chosen.size>5*1024*1024 ? 'Il file supera il limite di 5 MB.' : '';
    input.setCustomValidity(error);
    feedback.textContent=error;
    feedback.hidden=!error;
    if (!error) {
      if(source()) alt.value='';
      release();
      file=chosen;
      localURL=URL.createObjectURL(chosen);
    }
    display();
    refreshPhone();
  };
  remove.onclick=()=>{
    release();
    saved=null;
    file=null;
    input.value='';
    input.setCustomValidity('');
    alt.value='';
    feedback.hidden=true;
    display();
    refreshPhone();
  };
  alt.oninput=()=>{
    const img=$('img',holder);
    if(img) img.alt=alt.value.trim() || 'Illustrazione della domanda';
  };
  display();
  return {
    preview:()=>imageFigure(source(),alt.value),
    async payload(){
      const value={image:saved,imageAlt:source()?alt.value.trim():''};
      if(file) {
        const chosen=file;
        value.image=null;
        value.imageUpload=await new Promise((resolve,reject)=>{
          const reader=new FileReader();
          reader.onerror=()=>reject(new Error('Impossibile leggere l’immagine. Seleziona nuovamente il file.'));
          reader.onload=()=>resolve(reader.result.slice(reader.result.indexOf(',')+1));
          reader.readAsDataURL(chosen);
        });
      }
      return value;
    }
  };
}

function openQuestionImage(figure) {
  const original=$('img',figure), viewer=$('#question-image-viewer');
  if(!original || !viewer) return;
  const picture=$('img',viewer), zoom=$('[data-zoom-image]',viewer);
  picture.src=original.src;
  picture.alt=original.alt;
  const caption=$('.image-caption',viewer);
  caption.open=false;
  caption.hidden=!original.alt || original.alt==='Illustrazione della domanda';
  $('p',caption).textContent=original.alt;
  viewer.classList.remove('zoomed');
  zoom.setAttribute('aria-pressed','false');
  viewer.showModal();
  const viewport=$('.image-viewport',viewer);
  viewport.scrollTop=0;
  viewport.scrollLeft=0;
  $('[data-close-image]',viewer).focus();
}

function handleImageClick(target) {
  const figure=target.closest('.question-image');
  if(figure && target.closest('img, [data-expand-image]')) {
    openQuestionImage(figure);
    return true;
  }
  const viewer=target.closest('#question-image-viewer');
  if(!viewer) return false;
  if(target.closest('[data-close-image]')) viewer.close();
  const zoom=target.closest('[data-zoom-image]');
  if(zoom) zoom.setAttribute('aria-pressed',String(viewer.classList.toggle('zoomed')));
  return true;
}

function closeQuestionImage() {
  const viewer=$('#question-image-viewer');
  if(viewer?.open) viewer.close();
}
