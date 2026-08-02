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
  function removeItem(index) {
    const items = load();
    items.splice(index, 1);
    save(items);
  }

  function refreshBadges() {
    const c = count();
    const el = document.getElementById("cart-count");
    if (el) el.textContent = c;
    const bar = document.getElementById("cartbar");
    if (bar) {
      bar.hidden = c === 0;
      const bc = document.getElementById("cartbar-count");
      const bt = document.getElementById("cartbar-total");
      if (bc) bc.textContent = c;
      if (bt) bt.textContent = fcfa(subtotal());
    }
  }

  // --- Expose global helpers -------------------------------------------- //
  window.stepQty = function (delta) {
    const q = document.getElementById("qty");
    q.value = Math.max(1, (parseInt(q.value, 10) || 1) + delta);
  };

  window.addCurrentProduct = function () {
    const p = window.PRODUCT;
    const qty = Math.max(1, parseInt(document.getElementById("qty").value, 10) || 1);
    const sel = document.getElementById("variant");
    let variant_id = null, variant_name = null, price = p.base_price;
    if (sel) {
      const opt = sel.options[sel.selectedIndex];
      variant_id = parseInt(sel.value, 10);
      variant_name = opt.dataset.name;
      price = parseInt(opt.dataset.price, 10);
    }
    addItem({ product_id: p.id, variant_id, name: p.name, variant_name, price, quantity: qty, image: p.image });
    window.location.href = "/s/" + SLUG + "/panier";
  };

  window.renderCartPage = function () {
    const items = load();
    const box = document.getElementById("cart-items");
    const empty = document.getElementById("cart-empty");
    const summary = document.getElementById("cart-summary");
    if (!items.length) { if (empty) empty.hidden = false; return; }
    if (summary) summary.hidden = false;
    box.innerHTML = "";
    items.forEach((it, idx) => {
      const row = document.createElement("div");
      row.className = "card";
      row.innerHTML =
        '<div class="list-row"><div class="grow"><strong>' + escapeHtml(it.name) + "</strong>" +
        (it.variant_name ? ' <span class="muted">· ' + escapeHtml(it.variant_name) + "</span>" : "") +
        "<br><span class=\"muted\">" + fcfa(it.price) + "</span></div>" +
        '<button class="btn sm outline" data-rm="' + idx + '">🗑</button></div>' +
        '<div class="qty mt"><button data-dec="' + idx + '">−</button>' +
        '<input type="number" min="1" value="' + it.quantity + '" data-qty="' + idx + '" style="width:70px;text-align:center">' +
        '<button data-inc="' + idx + '">+</button>' +
        '<span class="grow right"><strong>' + fcfa(it.price * it.quantity) + "</strong></span></div>";
      box.appendChild(row);
    });
    document.getElementById("sum-subtotal").textContent = fcfa(subtotal());
    box.querySelectorAll("[data-rm]").forEach((b) => b.onclick = () => { removeItem(+b.dataset.rm); renderCartPage(); });
    box.querySelectorAll("[data-inc]").forEach((b) => b.onclick = () => { setQty(+b.dataset.inc, load()[+b.dataset.inc].quantity + 1); renderCartPage(); });
    box.querySelectorAll("[data-dec]").forEach((b) => b.onclick = () => { setQty(+b.dataset.dec, load()[+b.dataset.dec].quantity - 1); renderCartPage(); });
    box.querySelectorAll("[data-qty]").forEach((inp) => inp.onchange = () => { setQty(+inp.dataset.qty, parseInt(inp.value, 10) || 1); renderCartPage(); });
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
      '<div class="list-row"><div class="grow">' + escapeHtml(it.name) +
      (it.variant_name ? " · " + escapeHtml(it.variant_name) : "") +
      ' <span class="muted">x' + it.quantity + "</span></div><span>" + fcfa(it.price * it.quantity) + "</span></div>"
    ).join("");
    document.getElementById("co-subtotal").textContent = fcfa(subtotal());

    document.getElementById("checkout-form").addEventListener("submit", submitCheckout);
  };

  async function submitCheckout(e) {
    e.preventDefault();
    const btn = document.getElementById("submit-btn");
    const errBox = document.getElementById("checkout-error");
    errBox.hidden = true;
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
      if (!res.ok) throw new Error(data.detail || "Erreur lors de la commande.");
      // Succès : on garde la référence puis on redirige vers la confirmation serveur.
      window.location.href = "/s/" + SLUG + "/confirmation/" + data.order.reference;
    } catch (err) {
      errBox.textContent = err.message;
      errBox.hidden = false;
      btn.disabled = false; btn.textContent = "Valider et envoyer sur WhatsApp";
    }
  }

  window.clearCart = function () { localStorage.removeItem(KEY); };

  function val(id) { const el = document.getElementById(id); return el ? el.value.trim() : ""; }
  function escapeHtml(s) { return (s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

  // Variant price update on product page
  document.addEventListener("DOMContentLoaded", function () {
    refreshBadges();
    const sel = document.getElementById("variant");
    const unit = document.getElementById("unit-price");
    if (sel && unit) {
      sel.addEventListener("change", function () {
        const price = parseInt(sel.options[sel.selectedIndex].dataset.price, 10);
        unit.textContent = fcfa(price);
      });
    }
  });
})();
