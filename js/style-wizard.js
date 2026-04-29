/* CayenaBot — style-wizard.js
 * 6-step Style DNA wizard. Selections build a tag string injected into
 * every render prompt and tint material accents in scene-builder.
 */

const STEPS = [
  {
    id: 'architecture', label: 'Arquitectura',
    options: [
      { id: 'tropical-modern', name: 'Tropical Moderno', tags: 'tropical modern architecture, clean lines, flat roof, floor-to-ceiling windows, indoor-outdoor living' },
      { id: 'mediterranean', name: 'Mediterráneo', tags: 'Mediterranean architecture, white stucco, terracotta roof, arched windows, stone accents' },
      { id: 'minimalist', name: 'Minimalista', tags: 'minimalist contemporary architecture, exposed concrete, geometric forms, clean volumes' },
      { id: 'colonial-caribbean', name: 'Colonial Caribeño', tags: 'Caribbean colonial architecture, colorful facade, wooden balconies, high ceilings' },
      { id: 'industrial-loft', name: 'Loft Industrial', tags: 'industrial loft, exposed brick, steel beams, open floor plan, double height ceilings' },
      { id: 'eco-sustainable', name: 'Eco Sustentable', tags: 'eco sustainable architecture, green roof, natural materials, bamboo, solar panels, biophilic' },
      { id: 'brutalist', name: 'Brutalista', tags: 'brutalist architecture, raw concrete, massive geometric forms, dramatic shadows' },
      { id: 'art-deco', name: 'Art Deco', tags: 'art deco architecture, geometric decorative patterns, gold accents, glamorous facade' },
      { id: 'japanese-zen', name: 'Japonés Zen', tags: 'Japanese zen architecture, natural wood, stone gardens, water features, minimalist harmony' },
      { id: 'glass-modern', name: 'Vidrio Moderno', tags: 'glass and steel modern architecture, full transparency, visible structure, panoramic views' },
    ],
  },
  {
    id: 'interior', label: 'Interior',
    options: [
      { id: 'luxury-modern', name: 'Lujo Moderno', tags: 'luxury modern interior, marble floors, designer furniture, premium finishes, crystal chandeliers' },
      { id: 'scandinavian', name: 'Escandinavo', tags: 'Scandinavian interior, light wood, white walls, functional simplicity, hygge' },
      { id: 'boho-tropical', name: 'Boho Tropical', tags: 'bohemian tropical interior, rattan furniture, indoor plants, earth tones, macrame' },
      { id: 'contemporary-art', name: 'Arte Contemporáneo', tags: 'contemporary art gallery interior, statement pieces, gallery lighting' },
      { id: 'resort-spa', name: 'Resort Spa', tags: 'resort spa interior, zen atmosphere, natural stone, water features, ambient lighting' },
      { id: 'coastal-chic', name: 'Coastal Chic', tags: 'coastal chic interior, white and blue palette, driftwood accents, linen fabrics' },
      { id: 'mid-century', name: 'Mid-Century', tags: 'mid-century modern interior, walnut wood, organic curves, Eames furniture' },
      { id: 'maximalist', name: 'Maximalista', tags: 'maximalist interior, bold colors, mixed patterns, rich textures, jewel tones' },
      { id: 'wabi-sabi', name: 'Wabi-Sabi', tags: 'wabi-sabi interior, raw plaster walls, handmade ceramics, natural imperfections' },
    ],
  },
  {
    id: 'decoration', label: 'Decoración',
    options: [
      { id: 'tropical-plants', name: 'Plantas Tropicales', tags: 'lush tropical indoor plants, monstera, areca palms, ferns, living green walls' },
      { id: 'minimalist-decor', name: 'Minimalista', tags: 'minimalist decoration, few carefully chosen objects, negative space' },
      { id: 'artisan-crafts', name: 'Artesanía', tags: 'artisan handcrafted decor, handmade ceramics, woven baskets, carved wood' },
      { id: 'luxury-accents', name: 'Lujo', tags: 'luxury accent decor, gold fixtures, marble accessories, crystal vases, velvet' },
      { id: 'ocean-inspired', name: 'Océano', tags: 'ocean inspired decor, seashells, coral, driftwood art, blue glass, nautical' },
      { id: 'modern-art', name: 'Arte Moderno', tags: 'modern art decor, large abstract paintings, contemporary sculptures, gallery wall' },
      { id: 'vintage-eclectic', name: 'Vintage Ecléctico', tags: 'vintage eclectic decor, antique mirrors, retro lamps, mixed era furniture' },
      { id: 'caribbean-local', name: 'Caribeño Local', tags: 'Caribbean local decor, Dominican art, Taino inspired crafts, tropical colors, mahogany carvings' },
    ],
  },
  {
    id: 'materials', label: 'Materiales',
    options: [
      { id: 'marble-gold', name: 'Mármol + Oro', tags: 'Calacatta marble floors and countertops, brushed gold fixtures, Carrara marble bathroom' },
      { id: 'wood-stone', name: 'Madera + Piedra', tags: 'natural teak wood floors, oak cabinetry, natural stone walls, warm wood tones' },
      { id: 'concrete-glass', name: 'Concreto + Vidrio', tags: 'polished concrete floors, floor-to-ceiling tempered glass, exposed concrete walls' },
      { id: 'tropical-materials', name: 'Tropicales', tags: 'bamboo accents, rattan furniture, coral stone walls, teak decking, natural fibers' },
      { id: 'porcelain-premium', name: 'Porcelanato Premium', tags: 'large format porcelain tile floors, wood-effect porcelain, premium Italian tiles' },
      { id: 'mixed-textures', name: 'Texturas Mixtas', tags: 'mixed materials, exposed brick, reclaimed wood, black metal frames, textured fabrics' },
    ],
  },
  {
    id: 'palette', label: 'Paleta',
    options: [
      { id: 'warm-earth', name: 'Tierra Cálida', palette: ['#8B6914','#C4773B','#D4A76A','#F5E6CC','#2C1810'], tags: 'warm earth tones, terracotta, sand, cream' },
      { id: 'ocean-breeze', name: 'Brisa Oceánica', palette: ['#1B4965','#5FA8D3','#BEE9E8','#FFFFFF','#CAD2C5'], tags: 'ocean blue and white, coastal' },
      { id: 'monochrome', name: 'Monocromo', palette: ['#1a1a1a','#333333','#666666','#cccccc','#ffffff'], tags: 'monochrome, black white grey' },
      { id: 'tropical-vibrant', name: 'Tropical Vibrante', palette: ['#2D6A4F','#52B788','#F4A261','#E76F51','#264653'], tags: 'vibrant tropical, green, orange, coral' },
      { id: 'neutral-luxury', name: 'Neutro Lujoso', palette: ['#B8A898','#D4C5B5','#E8DDD3','#F5F0EB','#8C7B6B'], tags: 'neutral luxury, beige, taupe, warm grey' },
      { id: 'bold-contemporary', name: 'Contemporáneo Bold', palette: ['#000000','#FFFFFF','#C4773B','#2C3E50','#E74C3C'], tags: 'bold, black, white, copper, red' },
      { id: 'sage-blush', name: 'Salvia + Rubor', palette: ['#87A878','#D4C5B0','#E8C4C4','#F5E6D8','#4A5D3E'], tags: 'sage green and blush pink, feminine elegant' },
      { id: 'midnight-gold', name: 'Medianoche + Oro', palette: ['#0D1117','#1a1a2e','#C4773B','#D4A76A','#F5E6CC'], tags: 'midnight dark blue and gold, dramatic luxury' },
      { id: 'all-white', name: 'Blanco Total', palette: ['#FFFFFF','#F5F5F5','#EEEEEE','#E0E0E0','#FAFAFA'], tags: 'all white, pure white, bright clean minimal' },
      { id: 'terracotta', name: 'Terracota', palette: ['#C4773B','#A0522D','#D2691E','#DEB887','#F5DEB3'], tags: 'terracotta, burnt orange, sienna, warm clay' },
    ],
  },
  {
    id: 'lighting', label: 'Iluminación',
    options: [
      { id: 'golden-hour', name: 'Golden Hour', tags: 'golden hour warm lighting, long shadows, orange sun glow, magic hour' },
      { id: 'bright-midday', name: 'Mediodía', tags: 'bright midday natural light, blue sky, vivid colors, sharp details' },
      { id: 'overcast-soft', name: 'Nublado Suave', tags: 'overcast soft diffused lighting, even illumination, professional photography' },
      { id: 'twilight', name: 'Crepúsculo', tags: 'twilight blue hour, interior lights glowing, dark blue sky, dramatic mood' },
      { id: 'tropical-morning', name: 'Mañana Tropical', tags: 'tropical morning light, fresh atmosphere, bright green, cool shadows' },
      { id: 'dramatic-night', name: 'Noche Dramática', tags: 'dramatic night architecture lighting, illuminated pool, uplighting, stars' },
      { id: 'studio-light', name: 'Estudio', tags: 'professional studio lighting, perfectly balanced, no harsh shadows, magazine quality' },
    ],
  },
];

export function mountStyleWizard({ state, save, toast }) {
  const modal = document.getElementById('wizard-modal');
  const body = document.getElementById('wizard-body');
  const prevBtn = document.getElementById('wizard-prev');
  const nextBtn = document.getElementById('wizard-next');
  const stepLbl = document.getElementById('wizard-step-label');

  let stepIdx = 0;

  function render() {
    body.innerHTML = '';
    const step = STEPS[stepIdx];
    const wrapper = document.createElement('div');
    wrapper.className = 'wizard-step active';
    const h = document.createElement('h4');
    h.textContent = step.label;
    wrapper.appendChild(h);
    const opts = document.createElement('div');
    opts.className = 'wizard-options';
    const current = state.project?.styleDNA?.[step.id]?.id;

    step.options.forEach(opt => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'wizard-option' + (opt.id === current ? ' selected' : '');
      const strong = document.createElement('strong');
      strong.textContent = opt.name;
      btn.appendChild(strong);
      const em = document.createElement('em');
      em.textContent = (opt.tags || '').slice(0, 60) + '...';
      btn.appendChild(em);
      if (opt.palette) {
        const sw = document.createElement('div');
        sw.className = 'palette-swatches';
        opt.palette.forEach(c => {
          const s = document.createElement('span');
          s.style.background = c;
          sw.appendChild(s);
        });
        btn.appendChild(sw);
      }
      btn.onclick = () => {
        state.project.styleDNA = state.project.styleDNA || {};
        state.project.styleDNA[step.id] = { id: opt.id, name: opt.name, tags: opt.tags, palette: opt.palette };
        save?.();
        opts.querySelectorAll('.wizard-option').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
      };
      opts.appendChild(btn);
    });
    wrapper.appendChild(opts);
    body.appendChild(wrapper);

    stepLbl.textContent = `Paso ${stepIdx + 1} de ${STEPS.length}`;
    prevBtn.disabled = stepIdx === 0;
    nextBtn.textContent = stepIdx === STEPS.length - 1 ? 'Terminar' : 'Siguiente →';
  }

  prevBtn.onclick = () => { if (stepIdx > 0) { stepIdx--; render(); } };
  nextBtn.onclick = () => {
    if (stepIdx < STEPS.length - 1) { stepIdx++; render(); }
    else { modal.hidden = true; toast?.('Style DNA actualizado', 'success'); }
  };

  function open() {
    if (!state.project) return toast?.('Abre un proyecto primero', 'error');
    stepIdx = 0;
    modal.hidden = false;
    render();
  }

  return { open };
}
