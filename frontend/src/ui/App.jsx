import { useEffect, useRef, useState } from "react";
import { listChapters, getQuestions, addAnswer, storyChapter, getAnswers, storyCompile, getCurrentUser, setToken, logout, getStoryChapter, updateLanguage } from "../api";
import { createWebSpeechRecognizer } from "../lib/webspeech";
import Login from "./Login";

const translations = {
  he: {
    loading: "טוען...",
    selectChapter: "בחר פרק",
    convertChapter: "✍️ הפוך את הפרק לסיפור",
    questions: "שאלות",
    chapterStory: "Chapter Story",
    noQuestions: "אין שאלות לפרק זה עדיין.",
    recording: "🎙️ תמלול",
    stop: "⏹ עצור",
    placeholder: "אפשר להקליד תשובה או להשתמש בדיבור",
    saving: "שומר...",
    saved: "✓ נשמר",
    saveError: "שגיאה בשמירה",
    buildFullStory: "✨ הפוך את כל הפרקים לסיפור אחד",
    showFullStory: "📖 הצג את הסיפור",
    logout: "התנתק",
    backToInterface: "← חזרה לממשק",
    fullStoryTitle: "סיפור חייך המלא",
    noStoryYet: "עדיין לא נוצר סיפור לפרק זה.",
    clickToCreate: "לחץ על \"הפוך את הפרק לסיפור\" כדי ליצור סיפור.",
    loadingLong: "זה עלול לקחת כמה רגעים. אנא המתן...",
    storyCreated: "נוצר סיפור פרק ✨",
    storyError: "שגיאה ביצירת סיפור",
    fullStoryCreated: "נוצר סיפור מלא מכל הפרקים ✨",
    fullStoryError: "שגיאה ביצירת הסיפור המלא",
    recordingStarted: "הקלטה התחילה...",
    recordingError: "שגיאה בהקלטה:",
    micPermissionError: "נדרש אישור לשימוש במיקרופון. אנא בדוק את הגדרות הדפדפן.",
    languageUpdated: "שפה עודכנה ✨",
    languageError: "שגיאה בעדכון השפה",
    appTitle: "סיפור חייך – מערכת ריאיון",
  },
  en: {
    loading: "Loading...",
    selectChapter: "Select Chapter",
    convertChapter: "✍️ Convert Chapter to Story",
    questions: "Questions",
    chapterStory: "Chapter Story",
    noQuestions: "No questions for this chapter yet.",
    recording: "🎙️ Record",
    stop: "⏹ Stop",
    placeholder: "You can type an answer or use speech",
    saving: "Saving...",
    saved: "✓ Saved",
    saveError: "Error saving",
    buildFullStory: "✨ Turn All Chapters into One Story",
    showFullStory: "📖 Show Story",
    logout: "Logout",
    backToInterface: "← Back to Interface",
    fullStoryTitle: "Your Complete Life Story",
    noStoryYet: "No story has been created for this chapter yet.",
    clickToCreate: "Click \"Convert Chapter to Story\" to create a story.",
    loadingLong: "This may take a few moments. Please wait...",
    storyCreated: "Chapter story created ✨",
    storyError: "Error creating story",
    fullStoryCreated: "Full story created from all chapters ✨",
    fullStoryError: "Error creating full story",
    recordingStarted: "Recording started...",
    recordingError: "Recording error:",
    micPermissionError: "Microphone permission required. Please check your browser settings.",
    languageUpdated: "Language updated ✨",
    languageError: "Error updating language",
    appTitle: "Your Life Story – Interview System",
  },
};

export default function App() {
  const [user, setUser] = useState(null);
  const [loadingAuth, setLoadingAuth] = useState(true);
  const [chapters, setChapters] = useState([]);
  const [chapter, setChapter] = useState("");
  const [questions, setQuestions] = useState([]);
  const [personId, setPersonId] = useState(null);
  const [recording, setRecording] = useState(false);
  const [transcripts, setTranscripts] = useState({});
  const [interimTranscripts, setInterimTranscripts] = useState({});
  const [generatedStories, setGeneratedStories] = useState({}); // Store generated stories by chapter_id
  const [activeTab, setActiveTab] = useState("questions"); // "questions" or "story"
  const [fullStory, setFullStory] = useState(null); // Full compiled story from all chapters
  const [showFullStory, setShowFullStory] = useState(false); // Whether to show the full story page
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const recRef = useRef(null);
  const resultIndexRef = useRef(0);
  const activeQRef = useRef(null);
  const [activeQ, setActiveQ] = useState(null);
  const [saveStatus, setSaveStatus] = useState({}); // Track save status per question: 'saving', 'saved', 'unsaved'
  const saveTimeoutsRef = useRef({}); // Store debounce timeouts per question
  const questionsRef = useRef([]); // Store questions in ref for easy access
  
  // Get current language from user or default to Hebrew (reactive)
  const getCurrentLanguage = () => user?.language || localStorage.getItem("preferred_language") || "he";
  const getTranslations = () => translations[getCurrentLanguage()] || translations.he;
  
  // Get current language value for useEffect dependency
  const currentLanguage = getCurrentLanguage();
  
  // Update document direction and language based on current language
  useEffect(() => {
    const isRTL = currentLanguage === "he";
    
    // Update HTML dir attribute
    document.documentElement.dir = isRTL ? "rtl" : "ltr";
    
    // Update HTML lang attribute
    document.documentElement.lang = currentLanguage === "he" ? "he" : "en";
    
    // Update document title
    document.title = getTranslations().appTitle;
  }, [currentLanguage, user]);

  // Handle OAuth callback and check authentication
  useEffect(() => {
    const checkAuth = async () => {
      // Check for OAuth callback token in URL
      const urlParams = new URLSearchParams(window.location.search);
      const token = urlParams.get("token");
      
      if (token) {
        // Store token and clear URL
        setToken(token);
        window.history.replaceState({}, document.title, window.location.pathname);
      }

      // Try to get current user
      try {
        const userData = await getCurrentUser();
        setUser(userData);
        setPersonId(userData.person_id);
        // Sync language preference from user profile
        if (userData.language) {
          localStorage.setItem("preferred_language", userData.language);
        }
      } catch (error) {
        console.error("Auth error:", error);
        setUser(null);
        setPersonId(null);
      } finally {
        setLoadingAuth(false);
      }
    };

    checkAuth();
  }, []);

  useEffect(() => { 
    if (user) {
      const lang = user.language || "he";
      listChapters(lang)
        .then(chapters => {
          console.log("Loaded chapters:", chapters);
          setChapters(chapters || []);
        })
        .catch(err => {
          console.error("Error loading chapters:", err);
          // Try loading with default language if user language fails
          if (lang !== "he") {
            listChapters("he")
              .then(chapters => {
                console.log("Loaded chapters with default language:", chapters);
                setChapters(chapters || []);
              })
              .catch(err2 => {
                console.error("Error loading chapters with default language:", err2);
                setChapters([]);
              });
          } else {
            setChapters([]);
          }
        });
    }
  }, [user]);
  
  useEffect(() => { 
    if (chapter && user) {
      const lang = user.language || "he";
      getQuestions(chapter, lang).then(qs => {
        setQuestions(qs);
        questionsRef.current = qs; // Store in ref
      });
    } else {
      setQuestions([]);
      questionsRef.current = [];
    }
  }, [chapter, user]);
  
  // Load saved answers when chapter or personId changes
  useEffect(() => {
    if (chapter && personId) {
      // Clear transcripts when chapter changes to avoid mixing answers from different chapters
      setTranscripts({});
      
      getAnswers(personId, chapter)
        .then(answers => {
          // Convert array of answers to a map keyed by question_id
          const answersMap = {};
          answers.forEach(answer => {
            if (answer.question_id && answer.text) {
              answersMap[answer.question_id] = answer.text;
            }
          });
          // Load all saved answers for this chapter
          setTranscripts(answersMap);
        })
        .catch(err => {
          console.error("Error loading answers:", err);
          // Don't show error toast for empty answers (404 is expected if no answers exist)
        });
    } else {
      // Clear transcripts when chapter or personId is cleared
      setTranscripts({});
    }
  }, [chapter, personId]);

  // Load story chapter from database when chapter is selected
  useEffect(() => {
    if (chapter && user) {
      getStoryChapter(chapter)
        .then(storyData => {
          if (storyData && storyData.narrative) {
            // Load story from database into generatedStories state
            setGeneratedStories(prev => ({ ...prev, [chapter]: storyData.narrative }));
          }
        })
        .catch(err => {
          console.error("Error loading story chapter:", err);
          // Don't show error - story might not exist yet, which is fine
        });
    } else {
      // Clear story when chapter is cleared
      if (!chapter) {
        setGeneratedStories(prev => {
          const updated = { ...prev };
          // Don't clear all stories, just the one for the cleared chapter
          // Actually, we should keep all stories, just not show them
          return updated;
        });
      }
    }
  }, [chapter, user]);

  // Reset to questions tab when chapter changes
  useEffect(() => {
    setActiveTab("questions");
  }, [chapter]);

  // כשמתעדכנים בתמלול או הקלדה:
    function updateTranscript(qid, text) {
      setTranscripts(prev => ({ ...prev, [qid]: text }));
      // Clear interim transcript when user manually edits
      setInterimTranscripts(prev => ({ ...prev, [qid]: "" }));
    }


  function startRec(qid) {
    // Stop any existing recording first
    if (recRef.current) {
      recRef.current.stop();
    }
    
    // Reset result index for new recording session
    resultIndexRef.current = 0;
    
    try {
      const langCode = getCurrentLanguage() === "en" ? "en-US" : "he-IL";
      const rec = createWebSpeechRecognizer({ lang: langCode, interim: true });
      
      rec.onresult = (e) => {
        console.log("onresult called, results length:", e.results.length, "resultIndex:", resultIndexRef.current);
        let interimText = "";
        let newFinalText = "";
        
        // Process only new results (from resultIndex onwards)
        for (let i = resultIndexRef.current; i < e.results.length; i++) {
          const res = e.results[i];
          const transcript = res[0].transcript;
          console.log(`Result ${i}: isFinal=${res.isFinal}, transcript="${transcript}"`);
          
          if (res.isFinal) {
            newFinalText += transcript + " ";
            resultIndexRef.current = i + 1; // Update index after processing final result
          } else {
            // Get the last interim result (most recent)
            interimText = transcript;
          }
        }
        
        console.log("Processed - newFinalText:", newFinalText, "interimText:", interimText);
        
        // Append final results to the saved transcript
        if (newFinalText.trim()) {
          setTranscripts(prev => {
            const existing = prev[qid] || "";
            const updated = (existing + " " + newFinalText.trim()).trim();
            console.log(`Updating transcript for ${qid}: "${existing}" -> "${updated}"`);
            // Auto-save when recording adds final text
            setTimeout(() => {
              const question = questionsRef.current.find(q => q.id === qid);
              if (question && updated.trim()) {
                saveAnswer(question, false, updated);
              }
            }, 500); // Small delay to ensure state is updated
            return { ...prev, [qid]: updated };
          });
        }
        
        // Show interim results in real-time for this question
        if (interimText || newFinalText) {
          setInterimTranscripts(prev => {
            console.log(`Updating interim for ${qid}: "${interimText}"`);
            return { ...prev, [qid]: interimText };
          });
        }
      };
      
      rec.onend = () => {
        // If recording ended but we're still supposed to be recording, restart
        if (activeQRef.current === qid) {
          try {
            rec.start();
          } catch (e) {
            setRecording(false);
            setActiveQ(null);
            activeQRef.current = null;
            setInterimTranscripts(prev => ({ ...prev, [qid]: "" }));
          }
        } else {
          setRecording(false);
          setActiveQ(null);
          activeQRef.current = null;
          setInterimTranscripts(prev => ({ ...prev, [qid]: "" }));
        }
      };
      
      rec.onerror = (e) => {
        console.error("Speech recognition error:", e.error, e);
        if (e.error === "no-speech") {
          // This is normal when there's no speech detected, just restart
          if (activeQRef.current === qid) {
            try {
              rec.start();
            } catch (err) {
              console.error("Failed to restart:", err);
              setToast("שגיאה בהקלטה: " + err.message);
              setRecording(false);
              setActiveQ(null);
              activeQRef.current = null;
              setInterimTranscripts(prev => ({ ...prev, [qid]: "" }));
            }
          }
        } else if (e.error === "not-allowed") {
          setToast(getTranslations().micPermissionError);
          setRecording(false);
          setActiveQ(null);
          activeQRef.current = null;
          setInterimTranscripts(prev => ({ ...prev, [qid]: "" }));
        } else {
          setToast(getTranslations().recordingError + " " + e.error);
          setRecording(false);
          setActiveQ(null);
          activeQRef.current = null;
          setInterimTranscripts(prev => ({ ...prev, [qid]: "" }));
        }
      };
      
      rec.onstart = () => {
        console.log("Speech recognition started for question:", qid);
        setToast(getTranslations().recordingStarted);
        setTimeout(() => setToast(null), 2000);
      };
      
      rec.onaudiostart = () => {
        console.log("Audio capture started");
      };
      
      // Start the recognition
      try {
        rec.start();
        console.log("rec.start() called for question:", qid);
      } catch (startError) {
        console.error("Error starting recognition:", startError);
        setToast(getTranslations().recordingError + " " + startError.message);
        setRecording(false);
        setActiveQ(null);
        activeQRef.current = null;
        return;
      }
      recRef.current = rec;
      setRecording(true);
      setActiveQ(qid);
      activeQRef.current = qid;
      setInterimTranscripts(prev => ({ ...prev, [qid]: "" }));
    } catch (e) { 
      setToast(getTranslations().recordingError + " " + e.message);
      setRecording(false);
      setActiveQ(null);
    }
  }
  
  function stopRec() { 
    if (recRef.current) {
      recRef.current.stop();
    }
    const currentQ = activeQRef.current;
    setRecording(false);
    setActiveQ(null);
    activeQRef.current = null;
    if (currentQ) {
      setInterimTranscripts(prev => ({ ...prev, [currentQ]: "" }));
      // Auto-save when recording stops
      setTimeout(() => {
        const question = questionsRef.current.find(q => q.id === currentQ);
        if (question) {
          // Get current transcript value
          const text = transcripts[currentQ];
          if (text && text.trim()) {
            saveAnswer(question, false, text);
          }
        }
      }, 300);
    }
  }

async function saveAnswer(q, showToast = false, textOverride = null) {
  const text = textOverride || transcripts[q.id];
  if (!text || !text.trim()) {
    setSaveStatus(prev => ({ ...prev, [q.id]: 'unsaved' }));
    return;
  }
  
  setSaveStatus(prev => ({ ...prev, [q.id]: 'saving' }));
  try {
    await addAnswer({
      person_id: personId,
      chapter_id: chapter,
      question_id: q.id,
      text,
    });
    setSaveStatus(prev => ({ ...prev, [q.id]: 'saved' }));
    if (showToast) {
      setToast(getTranslations().saved);
    }
    // Clear saved status after 2 seconds
    setTimeout(() => {
      setSaveStatus(prev => {
        const updated = { ...prev };
        if (updated[q.id] === 'saved') {
          delete updated[q.id];
        }
        return updated;
      });
    }, 2000);
  } catch {
    setSaveStatus(prev => ({ ...prev, [q.id]: 'unsaved' }));
    if (showToast) {
      setToast(getTranslations().saveError);
    }
  }
}

// Auto-save with debouncing
function scheduleAutoSave(q) {
  // Clear existing timeout for this question
  if (saveTimeoutsRef.current[q.id]) {
    clearTimeout(saveTimeoutsRef.current[q.id]);
  }
  
  // Set new timeout (1.5 seconds after user stops typing)
  saveTimeoutsRef.current[q.id] = setTimeout(() => {
    saveAnswer(q, false); // Don't show toast for auto-save
    delete saveTimeoutsRef.current[q.id];
  }, 1500);
}

  async function buildChapterStory() {
    setLoading(true);
    try {
      const { narrative } = await storyChapter({ person_id: personId, chapter_id: chapter, style_guide: DEFAULT_STYLE, context_summary: "" });
      // Store the generated story
      setGeneratedStories(prev => ({ ...prev, [chapter]: narrative }));
      setToast(getTranslations().storyCreated);
      // Switch to the story tab
      setActiveTab("story");
    } catch { 
      setToast(getTranslations().storyError); 
    } finally { 
      setLoading(false); 
    }
  }

  const handleLogout = async () => {
    await logout();
    setUser(null);
    setPersonId(null);
    setChapters([]);
    setChapter("");
    setQuestions([]);
    setTranscripts({});
    setGeneratedStories({});
    setFullStory(null);
  };

  const handleLanguageChange = async (newLanguage) => {
    try {
      const updatedUser = await updateLanguage(newLanguage);
      setUser(updatedUser);
      localStorage.setItem("preferred_language", newLanguage);
      
      // Update direction immediately
      const isRTL = newLanguage === "he";
      document.documentElement.dir = isRTL ? "rtl" : "ltr";
      document.documentElement.lang = newLanguage === "he" ? "he" : "en";
      document.title = translations[newLanguage]?.appTitle || translations.he.appTitle;
      
      setToast(translations[newLanguage]?.languageUpdated || translations.he.languageUpdated);
    } catch (error) {
      console.error("Error updating language:", error);
      setToast(getTranslations().languageError);
    }
  };

  async function buildFullStory() {
    // If story already exists, just show it
    if (fullStory) {
      setShowFullStory(true);
      return;
    }

    setLoading(true);
    try {
      const response = await storyCompile({ 
        person_id: personId, 
        style_guide: DEFAULT_STYLE 
      });
      // API returns { compiled: True, book: book_text }
      const storyText = response.book || response.narrative || response;
      if (!storyText || storyText.trim() === "") {
        setToast("הסיפור ריק או לא התקבל מהשרת");
        setLoading(false);
        return;
      }
      // Save story to state and navigate to story page
      setFullStory(storyText);
      setShowFullStory(true);
      setToast(getTranslations().fullStoryCreated);
    } catch (err) {
      console.error("Error compiling full story:", err);
      setToast(getTranslations().fullStoryError);
    } finally {
      setLoading(false);
    }
  }

  // Show loading state while checking authentication
  if (loadingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-slate-50 to-slate-100">
          <div className="text-center">
            <div className="h-16 w-16 rounded-2xl bg-slate-900 text-white text-3xl flex items-center justify-center mx-auto mb-4 animate-pulse">
              📖
            </div>
            <p className="text-slate-600">{getTranslations().loading}</p>
          </div>
      </div>
    );
  }

  // Show login if not authenticated
  if (!user) {
    return <Login />;
  }

  // If showing full story, render the full story page
  if (showFullStory && fullStory) {
    return (
      <div className="min-h-screen p-6 sm:p-10 bg-gradient-to-b from-slate-50 to-slate-100">
        <header className="max-w-5xl mx-auto flex items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-2xl bg-white shadow flex items-center justify-center">📖</div>
            <h1 className="text-2xl sm:text-3xl font-semibold">{getTranslations().fullStoryTitle}</h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowFullStory(false)}
              className="rounded-xl bg-slate-900 text-white px-4 py-2 hover:bg-slate-800 transition"
            >
              {getTranslations().backToInterface}
            </button>
          </div>
        </header>

        <main className="max-w-5xl mx-auto">
          <section className="p-6 sm:p-8 rounded-2xl bg-white shadow">
            <div className="whitespace-pre-wrap text-slate-700 leading-relaxed text-base sm:text-lg">
              {fullStory}
            </div>
          </section>
        </main>

        {toast && (
          <div className="fixed bottom-4 right-4 bg-slate-900 text-white text-sm px-3 py-2 rounded-xl shadow" onClick={()=>setToast(null)}>
            {toast}
          </div>
        )}

        {/* Full-screen loader overlay */}
        {loading && (
          <div className="fixed inset-0 bg-black bg-opacity-50 backdrop-blur-sm z-50 flex items-center justify-center">
            <div className="bg-white rounded-2xl p-8 shadow-2xl max-w-md mx-4 text-center">
              <div className="mb-4">
                <div className="inline-block h-12 w-12 border-4 border-slate-200 border-t-slate-900 rounded-full animate-spin"></div>
              </div>
              <h3 className="text-xl font-semibold text-slate-900 mb-2">{t.loading}</h3>
              <p className="text-sm text-slate-600">
                {getTranslations().loadingLong}
              </p>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 sm:p-10 bg-gradient-to-b from-slate-50 to-slate-100">
      <header className="max-w-5xl mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-2xl bg-white shadow flex items-center justify-center">📖</div>
          <h1 className="text-2xl sm:text-3xl font-semibold">{getTranslations().appTitle}</h1>
        </div>
        <div className="flex items-center gap-2">
          {/* Language Selector */}
          <div className="flex items-center gap-1 border border-slate-300 rounded-xl overflow-hidden">
            <button
              onClick={() => handleLanguageChange("he")}
              className={`px-3 py-2 text-xs transition-colors ${
                user.language === "he"
                  ? "bg-slate-900 text-white"
                  : "bg-white text-slate-700 hover:bg-slate-50"
              }`}
              title="עברית"
            >
              ע
            </button>
            <button
              onClick={() => handleLanguageChange("en")}
              className={`px-3 py-2 text-xs transition-colors ${
                user.language === "en"
                  ? "bg-slate-900 text-white"
                  : "bg-white text-slate-700 hover:bg-slate-50"
              }`}
              title="English"
            >
              EN
            </button>
          </div>
          {user.picture && (
            <img 
              src={user.picture} 
              alt={user.name || "User"} 
              className="h-10 w-10 rounded-full border-2 border-white shadow"
            />
          )}
          {user.name && (
            <span className="text-sm text-slate-700 hidden sm:inline">{user.name}</span>
          )}
          <button
            onClick={buildFullStory}
            disabled={loading}
            className="rounded-xl bg-emerald-600 text-white px-4 py-2 text-sm hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {fullStory ? getTranslations().showFullStory : getTranslations().buildFullStory}
          </button>
          <button
            onClick={handleLogout}
            className="rounded-xl bg-slate-200 text-slate-700 px-4 py-2 text-sm hover:bg-slate-300 transition"
          >
            {getTranslations().logout}
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto mt-8 grid gap-6">
        <section className="p-4 sm:p-6 rounded-2xl bg-white shadow">
          <label className="block mb-2 text-sm text-slate-700">{getTranslations().selectChapter}</label>
          <div className="flex flex-wrap items-center gap-3">
            <select className="rounded-xl border border-slate-300 bg-white px-3 py-2" value={chapter} onChange={e=>setChapter(e.target.value)}>
              <option value="">—</option>
              {chapters.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
            </select>
            {chapter && <button onClick={buildChapterStory} disabled={loading || !!generatedStories[chapter]} className="rounded-xl border border-slate-300 px-3 py-2 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed">{getTranslations().convertChapter}</button>}
          </div>
        </section>

        {chapter && (
          <section className="p-4 sm:p-6 rounded-2xl bg-white shadow">
            {/* Tab Navigation */}
            <div className="flex gap-2 mb-6 border-b border-slate-200">
              <button
                onClick={() => setActiveTab("questions")}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === "questions"
                    ? "text-slate-900 border-b-2 border-slate-900"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {getTranslations().questions}
              </button>
              <button
                onClick={() => setActiveTab("story")}
                disabled={!generatedStories[chapter]}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  !generatedStories[chapter]
                    ? "text-slate-300 cursor-not-allowed"
                    : activeTab === "story"
                    ? "text-slate-900 border-b-2 border-slate-900"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {getTranslations().chapterStory}
              </button>
            </div>

            {/* Tab Content */}
            {activeTab === "questions" && (
              <div>
                {questions.length === 0 && <p className="text-slate-600">{getTranslations().noQuestions}</p>}
                <div className="grid gap-4">
                  {questions.map(q => (
                    <div key={q.id} className="border border-slate-200 rounded-2xl p-4 hover:shadow-sm transition">
                      <div className="flex items-start justify-between gap-4">
                        <strong className="text-slate-800">{q.order}. {q.text}</strong>
                        <div className="flex gap-2">
                          {!recording || activeQ !== q.id ? (
                            <button onClick={() => startRec(q.id)} className="rounded-xl bg-slate-900 text-white px-3 py-2 text-sm">{getTranslations().recording}</button>
                          ) : (
                            <button onClick={stopRec} className="rounded-xl bg-slate-200 px-3 py-2 text-sm">{getTranslations().stop}</button>
                          )}
                        </div>
                      </div>
                      <textarea
                        className="w-full mt-3 p-3 rounded-xl border border-slate-300 resize-none"
                        rows="4"
                        value={(transcripts[q.id] || "") + (activeQ === q.id && interimTranscripts[q.id] ? " " + interimTranscripts[q.id] : "")}
                        onChange={e => {
                          // When user manually edits, save the value and clear interim
                          const newValue = e.target.value;
                          setTranscripts(prev => ({ ...prev, [q.id]: newValue }));
                          setInterimTranscripts(prev => ({ ...prev, [q.id]: "" }));
                          // Schedule auto-save
                          scheduleAutoSave(q);
                          // Mark as unsaved while typing
                          setSaveStatus(prev => ({ ...prev, [q.id]: 'unsaved' }));
                        }}
                        placeholder={getTranslations().placeholder}
                      />
                      <div className="mt-2 flex items-center justify-between">
                        <div className="text-xs text-slate-500 flex items-center gap-2">
                          {saveStatus[q.id] === 'saving' && (
                            <span className="flex items-center gap-1">
                              <span className="animate-pulse">●</span>
                              {getTranslations().saving}
                            </span>
                          )}
                          {saveStatus[q.id] === 'saved' && (
                            <span className="flex items-center gap-1 text-emerald-600">
                              {getTranslations().saved}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === "story" && generatedStories[chapter] && (
              <div>
                <div className="whitespace-pre-wrap text-slate-700 leading-relaxed p-4 bg-slate-50 rounded-xl border border-slate-200 max-h-[600px] overflow-y-auto">
                  {generatedStories[chapter]}
                </div>
              </div>
            )}

            {activeTab === "story" && !generatedStories[chapter] && (
              <div className="text-center py-8 text-slate-500">
                <p>{getTranslations().noStoryYet}</p>
                <p className="text-sm mt-2">{getTranslations().clickToCreate}</p>
              </div>
            )}
          </section>
        )}
      </main>

      {toast && (
        <div className="fixed bottom-4 right-4 bg-slate-900 text-white text-sm px-3 py-2 rounded-xl shadow" onClick={()=>setToast(null)}>
          {toast}
        </div>
      )}

      {/* Full-screen loader overlay */}
      {loading && (
        <div className="fixed inset-0 bg-black bg-opacity-50 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-white rounded-2xl p-8 shadow-2xl max-w-md mx-4 text-center">
            <div className="mb-4">
              <div className="inline-block h-12 w-12 border-4 border-slate-200 border-t-slate-900 rounded-full animate-spin"></div>
            </div>
            <h3 className="text-xl font-semibold text-slate-900 mb-2">{t.loading}</h3>
            <p className="text-sm text-slate-600">
              {t.loadingLong}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

const DEFAULT_STYLE = `
גוף ראשון, עבר. טון חם, פשוט, לא מליצי.
תיאורים חושיים עדינים פעם-פעמיים. הימנעות מחזרות.
עקיבות בשמות, תאריכים ומקומות. 
`;
