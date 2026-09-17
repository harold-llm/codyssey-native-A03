"use strict";

const TIMEOUT_MS = 25000; // 백엔드 UPSTREAM_TIMEOUT(20초)보다 넉넉히
const $ = (id) => document.getElementById(id);

/* ---------- 네비게이션 & 다크 모드 ---------- */
const nav = $("nav");
$("navToggle").addEventListener("click", (e) => {
  const open = nav.classList.toggle("is-open");
  e.currentTarget.setAttribute("aria-expanded", String(open));
});
nav.addEventListener("click", (e) => {
  if (e.target.tagName === "A") nav.classList.remove("is-open");
});

const savedTheme = localStorage.getItem("theme");
if (savedTheme) document.documentElement.dataset.theme = savedTheme;
$("themeToggle").addEventListener("click", () => {
  const current =
    document.documentElement.dataset.theme ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("theme", next);
});

/* ---------- 토스트 ---------- */
let toastTimer;
function toast(text) {
  const el = $("toast");
  el.textContent = text;
  el.classList.add("is-show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("is-show"), 1800);
}

/* ---------- 하자 필드 토글 / 글자수 ---------- */
document.querySelectorAll('input[name="condition"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    const show = radio.value === "하자 있음";
    $("defectField").hidden = !show;
    if (!show) {
      $("defect").value = "";
      $("defectCount").textContent = "0";
    }
  });
});
$("defect").addEventListener("input", (e) => {
  $("defectCount").textContent = String(e.target.value.length);
  if (e.target.value.length >= 200) setMessage("formMessage", "하자 설명은 200자까지 입력할 수 있어요.");
});

function setMessage(id, text, ok = false) {
  const el = $(id);
  el.textContent = text;
  el.classList.toggle("message--ok", ok);
}

/* ---------- 생성 폼 ---------- */
let lastResult = null;

$("genForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  setMessage("formMessage", "");

  const form = e.currentTarget;
  const condition = form.querySelector('input[name="condition"]:checked');
  const payload = {
    category: $("category").value,
    itemName: $("itemName").value.trim(),
    usedPeriod: $("usedPeriod").value,
    condition: condition ? condition.value : "",
    defect: $("defect").value.trim(),
    price: $("price").value,
    trade: [...form.querySelectorAll('input[name="trade"]:checked')].map((c) => c.value),
    tone: $("tone").value,
  };

  // 실패 처리 ① 빈 입력 / 필수값 누락
  if (!payload.category || !payload.itemName || !payload.usedPeriod || !payload.condition || !payload.price) {
    setMessage("formMessage", "카테고리·물품명·사용 기간·상태·희망 금액은 필수입니다.");
    return;
  }
  if (payload.condition === "하자 있음" && !payload.defect) {
    setMessage("formMessage", "하자 내용을 입력해주세요.");
    return;
  }
  if (Number(payload.price) <= 0) {
    setMessage("formMessage", "희망 금액은 0원 초과 숫자로 입력해주세요.");
    return;
  }

  const btn = $("submitBtn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>생성 중...';

  // 실패 처리 ② 타임아웃
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    // 실패 처리 ③ API 오류 (4xx / 5xx)
    if (!res.ok) {
      setMessage("formMessage", res.status === 429
        ? "호출이 많아요. 1분 후 다시 시도해주세요."
        : "판매글을 만들지 못했어요. 잠시 후 다시 시도해주세요.");
      return;
    }

    // 실패 처리 ④ 비정상 응답 형식
    let data;
    try {
      data = await res.json();
    } catch {
      setMessage("formMessage", "결과를 읽는 데 실패했어요. 다시 시도해주세요.");
      return;
    }
    if (!data || !Array.isArray(data.titles) || !data.description) {
      setMessage("formMessage", "결과 형식이 올바르지 않아요. 다시 시도해주세요.");
      return;
    }

    render(data);
    setMessage("formMessage", "판매글이 생성되었어요.", true);
  } catch (err) {
    if (err.name === "AbortError") {
      setMessage("formMessage", "응답이 지연되고 있어요. 네트워크 확인 후 다시 시도해주세요.");
    } else {
      setMessage("formMessage", "네트워크 연결에 문제가 있어요. 다시 시도해주세요.");
    }
  } finally {
    clearTimeout(timer);
    btn.disabled = false;
    btn.textContent = "판매글 생성하기";
  }
});

function render(data) {
  lastResult = data;
  $("titleList").innerHTML = data.titles
    .map((t) => `<li>${escapeHtml(t)} <button class="btn btn--ghost" data-copy-text="${escapeHtml(t)}">복사</button></li>`)
    .join("");
  $("descBox").textContent = data.description;
  $("priceBox").textContent = data.price_comment || "-";
  $("tagBox").textContent = (data.hashtags || []).join(" ");
  $("result").hidden = false;
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ---------- 복사 ---------- */
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-copy], [data-copy-text]");
  if (!btn || !lastResult) return;
  let text = btn.dataset.copyText;
  if (btn.dataset.copy === "description") text = lastResult.description;
  if (btn.dataset.copy === "all") {
    text = [lastResult.titles[0], "", lastResult.description, "", lastResult.price_comment,
      (lastResult.hashtags || []).join(" ")].join("\n");
  }
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    toast("복사되었어요");
  } catch {
    toast("복사에 실패했어요");
  }
});

/* ---------- 문의 폼 (보너스 자동화) ---------- */
$("contactForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  setMessage("contactMessage", "");
  const email = $("email").value.trim();
  const content = $("content").value.trim();
  if (!email || !content) {
    setMessage("contactMessage", "이메일과 의견을 모두 입력해주세요.");
    return;
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    setMessage("contactMessage", "이메일 형식을 확인해주세요.");
    return;
  }

  const btn = $("contactBtn");
  btn.disabled = true;
  try {
    const res = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, content }),
    });
    if (!res.ok) throw new Error("fail");
    setMessage("contactMessage", "문의가 접수되었어요. 감사합니다!", true);
    e.currentTarget.reset();
  } catch {
    setMessage("contactMessage", "전송에 실패했어요. 잠시 후 다시 시도해주세요.");
  } finally {
    btn.disabled = false;
  }
});
