export function createWebSpeechRecognizer({ lang = "he-IL", interim = false } = {}) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) throw new Error("הדפדפן לא תומך ב-Web Speech API");
  const rec = new SR();
  rec.lang = lang;
  rec.interimResults = interim;
  rec.continuous = true;
  return rec;
}
