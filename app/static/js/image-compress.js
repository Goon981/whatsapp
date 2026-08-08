/* Réduction des photos avant envoi.

   Un téléphone récent produit des images de 3 à 5 Mo en 4000 px de large.
   Envoyées telles quelles depuis une connexion mobile, elles expliquent seules
   la lenteur de la création d'un produit : cinq photos représentaient jusqu'à
   20 Mo à téléverser. Aucune vitrine n'a besoin de plus de 1600 px.

   Le redimensionnement se fait dans le navigateur, sur un canvas : le serveur
   reçoit des fichiers dix à vingt fois plus légers, sans dépendance ajoutée ni
   traitement d'image côté serveur.

   Expose window.compressImage(file) -> Promise<File>. En cas d'échec (format
   exotique, canvas indisponible), le fichier d'origine est retourné tel quel :
   mieux vaut un envoi lent qu'un envoi impossible. */
(function () {
  const MAX_EDGE = 1600;   // côté le plus long, en pixels
  const QUALITY = 0.82;    // qualité JPEG, au-delà le gain devient négligeable
  const SKIP_BELOW = 300 * 1024;  // en dessous, la recompression n'apporte rien

  function canProcess(file) {
    return file && /^image\/(jpeg|png|webp)$/.test(file.type) && file.size > SKIP_BELOW;
  }

  function loadImage(file) {
    return new Promise(function (resolve, reject) {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = function () { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error("image illisible")); };
      img.src = url;
    });
  }

  function targetSize(width, height) {
    const longest = Math.max(width, height);
    if (longest <= MAX_EDGE) return [width, height];
    const ratio = MAX_EDGE / longest;
    return [Math.round(width * ratio), Math.round(height * ratio)];
  }

  window.compressImage = function (file) {
    if (!canProcess(file)) return Promise.resolve(file);

    return loadImage(file).then(function (img) {
      const [w, h] = targetSize(img.naturalWidth, img.naturalHeight);
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (!ctx) return file;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(img, 0, 0, w, h);

      return new Promise(function (resolve) {
        canvas.toBlob(function (blob) {
          // Un PNG à plat peut grossir une fois converti : ne garder le
          // résultat que s'il est réellement plus léger.
          if (!blob || blob.size >= file.size) { resolve(file); return; }
          const name = file.name.replace(/\.(png|webp|jpeg|jpg)$/i, "") + ".jpg";
          resolve(new File([blob], name, { type: "image/jpeg", lastModified: Date.now() }));
        }, "image/jpeg", QUALITY);
      });
    }).catch(function () { return file; });
  };

  /* Applique la compression à une liste de fichiers, en séquence : traiter
     cinq images de 12 Mpx en parallèle sature la mémoire d'un téléphone. */
  window.compressImages = async function (files) {
    const out = [];
    for (const file of files) out.push(await window.compressImage(file));
    return out;
  };
})();
