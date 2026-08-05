/* Panier client (localStorage) + checkout. Le total final est TOUJOURS recalculé
   côté serveur (RM-02) ; les prix stockés ici ne servent qu'à l'affichage. */
(function () {
  const SLUG = window.SHOP_SLUG || "shop";
  const KEY = "smartshop_cart_" + SLUG;

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY)) || []; }
    catch (e) { return []; }
  }
  function save(items) { localStorage.setItem(KEY, JSON.stringify(items)); refreshBadges(); }
  function fcfa(n) { return (n || 0).toLocaleString("fr-FR").replace(/ |,/g, " ") + " FCFA"; }
  function count(items) { return (items || load()).reduce((s, i) => s + i.quantity, 0); }
  function subtotal(items) { return (items || load()).reduce((s, i) => s + i.price * i.quantity, 0); }

  function addItem(item) {
    const items = load();
    const key = item.product_id + ":" + (item.variant_id || "");
    const existing = items.find((i) => i.product_id + ":" + (i.variant_id || "") === key);
    if (existing) existing.quantity += item.quantity;
    else items.push(item);
    save(items);
  }
  function setQty(index, qty) {
    const items = load();
    if (!items[index]) return;
    items[index].quantity = Math.max(1, qty);
    save(items);
  }
  function removeItem(index) { const items = load(); items.splice(index, 1); save(items); }

  function refreshBadges() {
    const c = count();
    const el = document.getElementById("cart-count");
    if (el) el.textContent = c;
    const bar = document.getElementById("cartbar");
    if (bar) {
      bar.classList.toggle("hide", c === 0);
      const bc = document.getElementById("cartbar-count");
      const bt = document.getElementById("cartbar-total");
      if (bc) bc.textContent = c;
      if (bt) bt.textContent = fcfa(subtotal());
    }
  }

  // --- Helpers exposés -------------------------------------------------- //
  window.stepQty = function (delta) {
    const q = document.getElementById("qty");
    q.value = Math.max(1, (parseInt(q.value, 10) || 1) + delta);
  };

  function readVariant() {
    const el = document.getElementById("variant");
    if (!el) return { id: null, name: null, price: null };
    if (el.tagName === "SELECT") {
      const opt = el.options[el.selectedIndex];
      return { id: parseInt(el.value, 10), name: opt.dataset.name, price: parseInt(opt.dataset.price, 10) };
    }
    return { id: parseInt(el.value, 10) || null, name: el.dataset.name || null, price: parseInt(el.dataset.price, 10) };
  }

  window.addCurrentProduct = function () {
    const p = window.PRODUCT;
    const qty = Math.max(1, parseInt(document.getElementById("qty").value, 10) || 1);
    const v = readVariant();
    addItem({
      product_id: p.id, variant_id: v.id, name: p.name,
      variant_name: v.name, price: v.price || p.base_price, quantity: qty, image: p.image,
    });
    window.location.href = "/s/" + SLUG + "/panier";
  };

  // Ajout direct depuis le catalogue (produit sans variante).
  window.quickAdd = function (id, name, price, image) {
    addItem({ product_id: id, variant_id: null, name: name, variant_name: null, price: price, quantity: 1, image: image });
    window.location.href = "/s/" + SLUG + "/panier";
  };
  function flashBadge() {
    const el = document.getElementById("cart-count");
    if (!el) return;
    el.style.transform = "scale(1.4)";
    setTimeout(() => (el.style.transform = "scale(1)"), 180);
  }

  window.renderCartPage = function () {
    const items = load();
    const box = document.getElementById("cart-items");
    const empty = document.getElementById("cart-empty");
    const summary = document.getElementById("cart-summary");
    if (!items.length) { if (empty) empty.classList.remove("hide"); return; }
    if (summary) summary.classList.remove("hide");
    box.innerHTML = "";
    items.forEach((it, idx) => {
      const row = document.createElement("div");
      row.className = "card tight";
      row.innerHTML =
        '<div class="row-item" style="padding:0;border:none">' +
        '<div class="th">' + (it.image ? '<img src="' + it.image + '" alt="">' : "🛒") + "</div>" +
        '<div class="grow"><div class="t1">' + escapeHtml(it.name) + "</div>" +
        (it.variant_name ? '<div class="t2">' + escapeHtml(it.variant_name) + "</div>" : "") +
        '<div class="t2 strong" style="color:var(--text)">' + fcfa(it.price) + "</div></div>" +
        '<button class="btn ghost" data-rm="' + idx + '" aria-label="Retirer">🗑</button></div>' +
        '<div class="qty mini mt8"><button data-dec="' + idx + '">−</button>' +
        '<input type="number" min="1" value="' + it.quantity + '" data-qty="' + idx + '">' +
        '<button data-inc="' + idx + '">＋</button>' +
        '<span class="grow right strong">' + fcfa(it.price * it.quantity) + "</span></div>";
      box.appendChild(row);
    });
    document.getElementById("sum-subtotal").textContent = fcfa(subtotal());
    box.querySelectorAll("[data-rm]").forEach((b) => (b.onclick = () => { removeItem(+b.dataset.rm); renderCartPage(); }));
    box.querySelectorAll("[data-inc]").forEach((b) => (b.onclick = () => { setQty(+b.dataset.inc, load()[+b.dataset.inc].quantity + 1); renderCartPage(); }));
    box.querySelectorAll("[data-dec]").forEach((b) => (b.onclick = () => { setQty(+b.dataset.dec, load()[+b.dataset.dec].quantity - 1); renderCartPage(); }));
    box.querySelectorAll("[data-qty]").forEach((inp) => (inp.onchange = () => { setQty(+inp.dataset.qty, parseInt(inp.value, 10) || 1); renderCartPage(); }));
  };

  window.togglePickup = function () {
    const on = document.getElementById("is_pickup").checked;
    document.getElementById("delivery-fields").style.display = on ? "none" : "block";
  };

  window.initCheckout = function () {
    const items = load();
    if (!items.length) { window.location.href = "/s/" + SLUG; return; }
    const box = document.getElementById("checkout-items");
    box.innerHTML = items.map((it) =>
      '<div class="li"><span>' + escapeHtml(it.name) +
      (it.variant_name ? " · " + escapeHtml(it.variant_name) : "") +
      ' <span class="muted">×' + it.quantity + "</span></span><span>" + fcfa(it.price * it.quantity) + "</span></div>"
    ).join("");
    document.getElementById("co-subtotal").textContent = fcfa(subtotal());
    document.getElementById("checkout-form").addEventListener("submit", submitCheckout);
  };

  async function submitCheckout(e) {
    e.preventDefault();
    const btn = document.getElementById("submit-btn");
    const errBox = document.getElementById("checkout-error");
    errBox.classList.add("hide");
    btn.disabled = true; btn.textContent = "Envoi en cours…";

    const isPickup = document.getElementById("is_pickup").checked;
    const zoneSel = document.getElementById("delivery_zone_id");
    const method = document.querySelector('input[name="payment_method"]:checked');
    const payload = {
      items: load().map((i) => ({ product_id: i.product_id, variant_id: i.variant_id, quantity: i.quantity })),
      customer_name: val("customer_name"),
      customer_phone: val("customer_phone"),
      payment_method: method ? method.value : "cash_on_delivery",
      is_pickup: isPickup,
      delivery_zone_id: (!isPickup && zoneSel && zoneSel.value) ? parseInt(zoneSel.value, 10) : null,
      delivery_city: val("delivery_city"),
      delivery_district: val("delivery_district"),
      delivery_details: val("delivery_details"),
      customer_note: val("customer_note"),
      marketing_consent: document.getElementById("marketing_consent").checked,
    };
    try {
      const res = await fetch("/api/shops/" + window.SHOP_ID + "/checkout", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Erreur lors de la commande.");
      window.location.href = "/s/" + SLUG + "/confirmation/" + data.order.reference;
    } catch (err) {
      errBox.textContent = err.message;
      errBox.classList.remove("hide");
      btn.disabled = false; btn.textContent = "🔒 Valider et envoyer sur WhatsApp";
    }
  }

  window.clearCart = function () { localStorage.removeItem(KEY); };

  function val(id) { const el = document.getElementById(id); return el ? el.value.trim() : ""; }
  function escapeHtml(s) { return (s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

  document.addEventListener("DOMContentLoaded", refreshBadges);
})();
