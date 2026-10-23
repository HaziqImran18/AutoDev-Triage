(() => {
  const $ = s => document.querySelector(s);
  const clock = $("#clock");
  if (clock) { const t = () => clock.textContent = new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}); t(); setInterval(t, 3e4); }

  const form = $("#triage-form");
  if (form) {
    const tok = $("#github_token"), rem = $("#remember");
    try { const saved = sessionStorage.getItem("gh_token"); if (saved) { tok.value = saved; rem.checked = true; } } catch (e) {}
    $("#eye").onclick = () => { tok.type = tok.type === "password" ? "text" : "password"; };
    const ov = $("#overlay"), items = [...ov.querySelectorAll(".ol li")], msg = $("#stepmsg");
    const texts = ["Diagnoser is reading the issue and parsing the stack trace…", "Researcher is searching the web for fixes…", "Integrator is writing the root cause report…"];
    form.addEventListener("submit", () => {
      try { rem.checked && tok.value ? sessionStorage.setItem("gh_token", tok.value) : sessionStorage.removeItem("gh_token"); } catch (e) {}
      ov.hidden = false; const t0 = Date.now(); let cur = -1;
      const tick = () => {
        const s = (Date.now() - t0) / 1e3, i = s < 9 ? 0 : s < 22 ? 1 : 2;
        $("#elapsed").textContent = Math.floor(s);
        if (i !== cur) { cur = i; items.forEach((li, k) => li.className = k < i ? "ok" : k === i ? "on" : ""); msg.textContent = texts[i]; }
      };
      tick(); setInterval(tick, 500);
    });
    addEventListener("pageshow", e => { if (e.persisted) ov.hidden = true; });
  }

  // render markdown safely (sanitized); falls back to plain text if CDN is blocked
  document.querySelectorAll(".md").forEach(el => {
    if (window.marked && window.DOMPurify) { el.innerHTML = DOMPurify.sanitize(marked.parse(el.textContent)); el.classList.add("on"); el.querySelectorAll("a").forEach(a => { a.target = "_blank"; a.rel = "noopener"; }); }
  });
  const raw = $("#raw");
  const copy = $("#copy"), dl = $("#download");
  if (copy) copy.onclick = async () => { await navigator.clipboard.writeText(raw.value); copy.textContent = "✓ Copied"; setTimeout(() => copy.textContent = "Copy report", 1500); };
  if (dl) dl.onclick = () => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([raw.value], {type: "text/markdown"})); a.download = "rca-report.md"; a.click(); };
})();
