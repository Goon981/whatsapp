/* Choix de la couleur de boutique : pastilles, sélecteur libre et aperçu.
   Partagé par la création de boutique et les réglages.

   La palette est calculée par le serveur (app/services/theme.py) et récupérée
   via /app/theme-preview. Une version JavaScript existait auparavant dans le
   gabarit de création, avec sa propre formule de contraste : les deux ont
   divergé, et l'aperçu ne montrait plus ce que les pages affichaient. */
(function () {
  const field = document.getElementById("theme_color");
  const preview = document.getElementById("theme-preview");
  if (!field || !preview) return;

  const hexOut = document.getElementById("theme-hex");
  const nameOut = document.getElementById("theme-name");
  const swatches = Array.from(document.querySelectorAll(".swatch"));
  let pending = null;

  function paint(palette) {
    for (const key of Object.keys(palette)) {
      preview.style.setProperty("--" + key, palette[key]);
    }
  }

  function markActive(hex) {
    const wanted = (hex || "").toLowerCase();
    let matched = null;
    swatches.forEach(function (s) {
      const on = s.dataset.color.toLowerCase() === wanted;
      s.classList.toggle("active", on);
      s.setAttribute("aria-pressed", on ? "true" : "false");
      if (on) matched = s.title;
    });
    if (nameOut) nameOut.textContent = matched || "Personnalisée";
    if (hexOut) hexOut.textContent = wanted;
  }

  function refresh(hex) {
    markActive(hex);
    clearTimeout(pending);
    /* Le sélecteur natif émet un évènement à chaque pixel parcouru : sans ce
       délai, glisser dans le nuancier déclencherait des dizaines d'appels. */
    pending = setTimeout(function () {
      fetch("/app/theme-preview?color=" + encodeURIComponent(hex))
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) { if (data) paint(data.light); })
        .catch(function () { /* aperçu indisponible : le formulaire reste utilisable */ });
    }, 120);
  }

  swatches.forEach(function (s) {
    s.addEventListener("click", function () {
      field.value = s.dataset.color;
      refresh(s.dataset.color);
    });
  });
  field.addEventListener("input", function () { refresh(field.value); });

  refresh(field.value);
})();
