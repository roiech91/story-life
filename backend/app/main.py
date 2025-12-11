
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from contextlib import asynccontextmanager
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from urllib.parse import urlencode

from app.config import get_settings
from app.llm import LifeStoryLLM
from app.database import init_db, get_db, get_db_context
from app.models import User, Chapter, Answer, Story, StoryChapter
from app.auth import (
    create_access_token,
    get_current_user,
    get_optional_current_user,
    get_or_create_user_from_oauth,
    get_google_oauth_client,
    get_google_user_info,
)

# Global LLM instance
llm: Optional[LifeStoryLLM] = None


def seed_chapters(db: Session):
    """Seed the chapters table with predefined chapters in both languages."""
    chapters_data_he = [
        {"id": "1-he", "title": "שורשים ומשפחה מוקדמת", "order": 1, "language": "he"},
        {"id": "2-he", "title": "ילדות", "order": 2, "language": "he"},
        {"id": "3-he", "title": "נעורים", "order": 3, "language": "he"},
        {"id": "4-he", "title": "אהבה וזוגיות", "order": 4, "language": "he"},
        {"id": "5-he", "title": "צבא / שירות / לימודים", "order": 5, "language": "he"},
        {"id": "6-he", "title": "קריירה ועשייה", "order": 6, "language": "he"},
        {"id": "7-he", "title": "הורות ומשפחה", "order": 7, "language": "he"},
        {"id": "8-he", "title": "חברים וקהילה", "order": 8, "language": "he"},
        {"id": "9-he", "title": "תחביבים ופנאי", "order": 9, "language": "he"},
        {"id": "10-he", "title": "אמונות וערכים", "order": 10, "language": "he"},
        {"id": "11-he", "title": "רגעים קשים ומשמעותיים", "order": 11, "language": "he"},
        {"id": "12-he", "title": "חלומות והבטים קדימה", "order": 12, "language": "he"},
    ]
    
    chapters_data_en = [
        {"id": "1-en", "title": "Roots and Early Family", "order": 1, "language": "en"},
        {"id": "2-en", "title": "Childhood", "order": 2, "language": "en"},
        {"id": "3-en", "title": "Teenage Years", "order": 3, "language": "en"},
        {"id": "4-en", "title": "Love and Relationships", "order": 4, "language": "en"},
        {"id": "5-en", "title": "Military / Service / Studies", "order": 5, "language": "en"},
        {"id": "6-en", "title": "Career and Work", "order": 6, "language": "en"},
        {"id": "7-en", "title": "Parenthood and Family", "order": 7, "language": "en"},
        {"id": "8-en", "title": "Friends and Community", "order": 8, "language": "en"},
        {"id": "9-en", "title": "Hobbies and Leisure", "order": 9, "language": "en"},
        {"id": "10-en", "title": "Beliefs and Values", "order": 10, "language": "en"},
        {"id": "11-en", "title": "Difficult and Meaningful Moments", "order": 11, "language": "en"},
        {"id": "12-en", "title": "Dreams and Looking Forward", "order": 12, "language": "en"},
    ]
    
    all_chapters = chapters_data_he + chapters_data_en
    
    # Delete old format chapters (without language suffix) if they exist
    old_chapters = db.query(Chapter).filter(
        ~Chapter.id.contains("-he"),
        ~Chapter.id.contains("-en")
    ).all()
    if old_chapters:
        print(f"⚠️  Found {len(old_chapters)} old-format chapters. Deleting them...")
        for old_ch in old_chapters:
            db.delete(old_ch)
        db.commit()
    
    # Add or update chapters
    for chapter_data in all_chapters:
        existing = db.query(Chapter).filter(Chapter.id == chapter_data["id"]).first()
        if not existing:
            chapter = Chapter(**chapter_data)
            db.add(chapter)
        else:
            # Update existing chapter if title or order changed
            existing.title = chapter_data["title"]
            existing.order = chapter_data["order"]
            existing.language = chapter_data["language"]
    
    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for app startup/shutdown."""
    global llm
    # Startup
    settings = get_settings()
    
    # Initialize database
    try:
        init_db()
        # Seed chapters
        with get_db_context() as db:
            seed_chapters(db)
        print("Database initialized and chapters seeded successfully")
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")
    
    # Initialize LLM
    try:
        llm = LifeStoryLLM(settings)
    except Exception as e:
        # If LLM initialization fails (e.g., missing API keys), log but continue
        # The endpoints will handle this gracefully
        print(f"Warning: LLM initialization failed: {e}")
        llm = None
    
    yield
    
    # Shutdown
    llm = None


app = FastAPI(title="Life Story Q&A API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Keep RAW_QUESTIONS for backward compatibility and question generation
# Structure: RAW_QUESTIONS[language][chapter_id] = [list of questions]
RAW_QUESTIONS: Dict[str, Dict[str, List[str]]] = {
    "he": {
    "1": [
        "איך קוראים לך? בן כמה אתה? ואיפה נולדת? ",
        "איפה נולדת, ומה אתה זוכר מהמקום שבו התחלת את חייך?",
        "מה הסיפור מאחורי השם שלך — מי בחר אותו ולמה דווקא הוא?",
        "מהו הזיכרון הראשון שלך כילד או ילדה?",
        "איך נראה הבית שבו גדלת — הריחות, הצלילים, התחושות?",
        "מי היו האנשים שחיו איתך בבית, ואיך הייתם מסתדרים?",
        "אילו חגים היו הכי משמעותיים בבית שלכם, ואיך חגגתם אותם?",
        "מה המאכל שהכי אהבת בילדותך, ומי היה מכין אותו?",
        "תוכל לספר על סיפור מצחיק או מביך שקרה לך כילד?",
        "מי היה האדם הקרוב אליך ביותר בילדות — ומדוע?",
        "אילו משחקים או פעילויות אהבת לעשות כשהיית קטן?",
        "מי היה החבר או החברה הכי טובים שלך בילדות, ומה אהבתם לעשות יחד?",
        "אילו שירים, סיפורים או מנגינות זכורים לך מהבית?",
        "מה למדת מאמא שלך — לאו דווקא במילים, אלא מההתנהגות שלה?",
        "ומה למדת מאבא שלך?",
        "אילו אמונות, ערכים או משפטים “קבועים” היו נשמעים בבית שלך?",
        "תאר רגע משפחתי שאתה זוכר כחמים במיוחד?",
        "האם היה מישהו במשפחה שכולם צחקו בזכותו, או שהיה “הליצן” של המשפחה?",
        "אילו מסורות או הרגלים משפחתיים הכי אהבת?",
        "האם היו במשפחה סיפורים שעברו מדור לדור — על נדודים, עלייה, אהבה, או הישרדות?",
        "איך נראתה השכונה או הכפר שבו גדלת? מי היו האנשים שסבבו אותך?",
        "איך התמודדה המשפחה עם רגעים קשים או מאתגרים?",
        "איזה ריח או טעם מייד מחזיר אותך הביתה?",
        "אם היית צריך לבחור תמונה אחת שמייצגת את הבית שבו גדלת — איזו תמונה זו הייתה?",
        "מה אתה חושב שירשת מהמשפחה שלך — תכונה, הרגל או גישה לחיים?",
        "אם היית יכול לדבר עם אחד מאבות המשפחה שלך, מי זה היה ומה היית שואל אותו?"
    ],
    "2": [
        "איפה בילית את רוב זמנך כילד? בבית, בחוץ, אצל חברים, בטבע?",
        "מי היה החבר או החברה הכי טובים שלך בילדות, ומה אהבתם לעשות יחד?",
        "איזה משחק או צעצוע היה האהוב עליך ביותר?",
        "מה המאכל או הממתק שהכי שימחו אותך כילד?",
        "היה לך מקום סודי או מיוחד שאהבת להיות בו לבד?",
        "איזה ריח או טעם מזכיר לך מיד את הילדות שלך?",
        "מהו אחד הזיכרונות הראשונים שלך מהגן או מבית הספר?",
        "איזה מורה או גננת השפיעו עליך במיוחד — ולמה?",
        "איך היית מתאר את עצמך כילד? ביישן, סקרן, שובב, רגוע...?",
        "מה גרם לך לצחוק הכי חזק כשהיית קטן?",
        "תוכל לספר סיפור מצחיק או מוזר שקרה לך בילדות?",
        "ממה פחדת כשהיית קטן — ומה היה עוזר לך להירגע?",
        "מה גרם לך להרגיש מוגן או נאהב?",
        "האם היו בבית חיות מחמד? מה זכור לך מהן?",
        "איזה תחביבים או עיסוקים אהבת לעשות לבד?",
        "איך נראו ימי ההולדת שלך? מי היה מגיע, ואיך חגגתם?",
        "מה היה חלום הילדות שלך — מה רצית להיות כשתגדל?",
        "האם הייתה תקופה בילדות שלך שאתה זוכר במיוחד לטובה? למה דווקא היא?",
        "תוכל לתאר יום טיפוסי בילדותך — מהבוקר עד הערב?",
        "מה היה קורה כשעשית משהו שובב או לא הקשבת להורים?",
        "אילו חופשות, טיולים או חוויות משפחתיות זכורות לך במיוחד?",
        "אם היית יכול לחזור ליום אחד בילדותך — לאיזה יום היית חוזר?",
        "מי היה הגיבור או הדמות שהערצת בילדותך — מסרט, ספר או מהחיים?",
        "מה למדת על עצמך כילד שהולך איתך עד היום?",
        "אם היית צריך לתאר את הילדות שלך במילה אחת — איזו מילה זו הייתה?"
    ],
    "3": [
        "באיזה גיל אתה מרגיש שהתחילו באמת ה\"נעורים\" שלך?",
        "איך נראית התקופה הזו עבורך — היית יותר מרדן, סקרן, רומנטיקן, ביישן?",
        "תוכל לתאר איך נראית השכונה, העיר או בית הספר באותן שנים?",
        "מי היו החברים הקרובים שלך בגיל ההתבגרות? מה חיבר ביניכם?",
        "איזה מוזיקה שמעת אז — ואיזה שיר ישר מחזיר אותך לתקופה ההיא?",
        "היה לך מקום קבוע שבו הייתם נפגשים — גג, גינה, קניון, חוף?",
        "איך היית מתלבש אז? היו סגנונות או טרנדים שמזוהים איתך?",
        "מה היה גורם לך להרגיש \"שייך\"?",
        "מתי בפעם הראשונה הרגשת שאתה שונה — במחשבה, בטעם, או בדרך שבה אתה רואה את העולם?",
        "אילו תחביבים או עיסוקים מילאו את זמנך אז?",
        "תוכל לספר על אהבה ראשונה — איך זה התחיל, איך זה נגמר, מה למדת מזה?",
        "מי היה המודל לחיקוי שלך באותה תקופה?",
        "איך היו היחסים עם ההורים באותן שנים?",
        "האם הרגשת חופש או מגבלות בבית / בבית הספר?",
        "מתי בפעם הראשונה עמדת על שלך או עשית משהו \"בניגוד לחוקים\"?",
        "מה היה החלום שלך אז לגבי העתיד?",
        "אם היית צריך לבחור רגע אחד שמסמל את הנעורים שלך — מהו?",
        "איך חווית את בית הספר התיכון — למדת ברצון, השתעממת, חיפשת את עצמך?",
        "היה לך מורה או מדריך שנשאר לך בזיכרון במיוחד?",
        "איך נראתה תקופת הבגרויות או סיום בית הספר עבורך?",
        "אילו חופשות, טיולים או חוויות קבוצתיות אתה זוכר מהתקופה הזו?",
        "אם היית יכול לדבר היום עם עצמך בגיל 16, מה היית אומר לו?",
        "איך נראתה החברות הראשונה שלך — מה למדת ממנה על עצמך?",
        "מה היית רוצה שילדיך או נכדיך ידעו עליך בגיל הזה?",
        "באיזו מילה אחת היית מתאר את תקופת הנעורים שלך?"
    ],
    "4": [
        "מתי בפעם הראשונה הרגשת אהבה? איך זה הרגיש?",
        "אתה זוכר את הפעם הראשונה שהתאהבת באמת? איך התחיל הקשר הזה?",
        "מה משך אותך באדם שאהבת לראשונה?",
        "איך היית מתאר את עצמך במערכות יחסים בגיל צעיר?",
        "מה למדת על עצמך מהאהבה הראשונה שלך?",
        "איך נראתה תקופת החיזור אצלך — מה היה נחשב “רומנטי”?",
        "תוכל לספר על רגע מצחיק או מביך שקרה לך באחת האהבות שלך?",
        "איך ידעת שפגשת אדם שאתה רוצה לחלוק איתו את חייך?",
        "מה גרם לך להרגיש ביטחון ואמון בקשר זוגי?",
        "אילו תכונות חיפשת או הערכת בבן/בת זוג?",
        "איך היו נראים הרגעים הקטנים של אהבה — לא המחוות הגדולות, אלא היומיום?",
        "תוכל לתאר רגע שבו הרגשת אהוב באמת?",
        "איך התמודדתם עם חילוקי דעות או תקופות קשות בזוגיות?",
        "מה למדת על תקשורת ואמון ממערכות היחסים שלך?",
        "אילו ערכים היו חשובים לך בתוך זוגיות?",
        "אם הייתה תקופה של פרידה או לב שבור — מה עזר לך לעבור אותה?",
        "איך השתנתה בעיניך המשמעות של אהבה לאורך השנים?",
        "אילו דמויות או זוגות בחייך היו עבורך מודל לאהבה טובה?",
        "איך הרגשת ביום שבו נישאת (אם נישאת)? מה אתה זוכר מהרגעים סביב זה?",
        "איזה שיר, מקום או ריח מזכיר לך אהבה גדולה?",
        "האם אתה חושב שיש דבר כזה “אהבה אחת ויחידה”?",
        "מה גורם לזוגיות להחזיק לאורך זמן, לדעתך?",
        "אם היית צריך לייעץ לנכד/ה שלך על אהבה — מה היית אומר?",
        "מה הכי מרגש אותך בזוגיות שלך עד היום?",
        "מה למדת על אהבה — במובן העמוק ביותר של המילה?"
    ],
    "5": [
        "איך הרגשת כשעמדת לפני השלב הזה — גיוס, שירות לאומי, או תחילת לימודים?",
        "איך בחרת את המסלול שלך — זה היה חלום, החלטה רציונלית או פשוט מה שיצא?",
        "תוכל לתאר את היום הראשון שלך בצבא או בלימודים? מה עובר לך בראש כשאתה נזכר בו?",
        "מי היו האנשים הראשונים שהכרת שם, והאם נשארתם בקשר?",
        "אילו תכונות שלך בלטו במיוחד בתקופה הזו?",
        "היה מישהו שראית בו מפקד, מדריך או מורה לחיים? מה למדת ממנו?",
        "תוכל לספר על חוויה משמעותית במיוחד מהשירות או מהלימודים?",
        "היה רגע שבו הרגשת גאווה אמיתית בעצמך?",
        "ומה עם רגע קשה — איך התמודדת איתו?",
        "איך השתנתה הדרך שבה ראית את עצמך באותה תקופה?",
        "האם זו הייתה תקופה של חופש ועצמאות או של אתגרים ולחצים?",
        "אילו חברויות נוצרו לך שם, ומה היה מיוחד בהן?",
        "תוכל לתאר סיטואציה מצחיקה או בלתי נשכחת מהשירות או מהקמפוס?",
        "אם למדת מקצוע — למה דווקא אותו, והאם אתה חושב שזה היה הבחירה הנכונה?",
        "האם היו אנשים שפתחו לך דלת או האמינו בך במיוחד?",
        "איך נראו הימים שלך — שגרה, משימות, לימודים, חופשות?",
        "מה היה בשבילך הדבר הכי מאתגר באותה תקופה?",
        "האם היה רגע שבו הרגשת שאתה מתבגר באמת?",
        "איך שמרת על קשר עם הבית והמשפחה בתקופה הזו?",
        "האם התגעגעת למשהו מהחיים שלפני כן?",
        "תוכל לתאר מקום מסוים מהשירות או מהלימודים שנחרט לך בזיכרון?",
        "מה למדת שם על אנשים — על חברות, על אמון, על שיתופי פעולה?",
        "האם היו חלומות או תכניות שצמחו באותן שנים?",
        "איך התקופה הזו תרמה לעיצוב מי שאתה היום?",
        "אם היית יכול לפגוש את עצמך ביום השחרור או סיום הלימודים — מה היית אומר לעצמך?"
    ],
    "6": [
        "מה הייתה העבודה או העיסוק הראשון שלך? איך הגעת אליו?",
        "איך הרגשת ביום הראשון שלך בעבודה?",
        "מי היה האדם הראשון שלימד אותך “איך הדברים באמת עובדים”?",
        "מה גרם לך לבחור במקצוע או בתחום שבו עסקת רוב חייך?",
        "אילו ערכים ניסית להביא איתך לעבודה?",
        "היה רגע שבו הרגשת שאתה “במקום הנכון”?",
        "ומה עם רגע שבו הרגשת תקוע או מאוכזב?",
        "מה למדת על עצמך דרך העבודה?",
        "איך היית מתאר את היחסים שלך עם קולגות, עובדים או מנהלים?",
        "תוכל לספר על החלטה מקצועית משמעותית שקיבלת — ומדוע?",
        "היה פרויקט, משימה או הישג שאתה זוכר בגאווה מיוחדת?",
        "אם היית צריך לבחור תכונה אחת שעזרה לך להצליח — מה היא?",
        "איך הצלחת לשמור על איזון בין עבודה לבית ולחיים האישיים?",
        "היו רגעים שבהם שקלת לשנות כיוון? מה גרם לך להישאר או לעבור?",
        "תוכל לתאר אדם בעבודה שהשפיע עליך במיוחד?",
        "איך היית מתמודד עם לחץ או עם מצבים לא פשוטים בעבודה?",
        "מה גרם לך תחושת משמעות אמיתית בעשייה שלך?",
        "האם הייתה תקופה שבה עבדת קשה במיוחד, ומה למדת ממנה?",
        "אם ניהלת אנשים — מה למדת על הנהגה ועל עבודה עם אחרים?",
        "אילו לקחים היית רוצה להעביר לדור הצעיר על קריירה ובחירות מקצועיות?",
        "איך היית מתאר את עצמך כעובד או כעמית לצוות?",
        "מהו הרגע שבו הכי הרגשת מוערך בעבודה?",
        "ומהו הרגע שבו היית צריך להתחזק או לעמוד על שלך?",
        "אם היית יכול לחזור אחורה — האם היית בוחר באותו מסלול?",
        "איך היית רוצה שיזכרו את העשייה שלך — מה החותם שהשארת?"
    ],
    "7": [
        "תמיד רצית להיות הורה?",
        "אתה זוכר את הרגע שבו הפכת להורה? איך הרגשת באותו יום?",
        "איך בחרתם את השמות לילדים שלכם? יש מאחוריהם סיפור מיוחד?",
        "מה השתנה בחיים שלך מרגע שנולדו הילדים?",
        "איך היית מתאר את עצמך כהורה בתחילת הדרך?",
        "מה היה הדבר שהכי הפחיד אותך בהורות — ומה היה הדבר הכי מרגש?",
        "מהו זיכרון ילדות חזק שלך מהתקופה שבה הילדים היו קטנים?",
        "אילו רגעים משפחתיים יומיומיים אתה זוכר באהבה?",
        "היה טקס, מסורת או הרגל משפחתי שהיה חשוב לך לשמור עליו בבית?",
        "איך נראתה השגרה שלכם כמשפחה?",
        "מה למדת מהילדים שלך — אולי משהו שלא ציפית ללמוד?",
        "היה רגע שבו הבנת שאתה באמת “הורה”?",
        "איך התמודדתם עם אתגרים או קשיים — בריאותיים, כלכליים או רגשיים?",
        "תוכל לספר על רגע שבו הרגשת גאווה אמיתית בילדיך?",
        "ומה עם רגע של דאגה או פחד גדול?",
        "איך חילקתם את האחריות בבית — מי עשה מה, ואיך זה עבד?",
        "אילו ערכים ניסית להעביר לילדיך?",
        "איך נראתה אצלכם ארוחת ערב משפחתית — על מה דיברתם, איך הייתה האווירה?",
        "אילו הרגלים או מנהגים מהבית שלך ניסית לשמר — ואילו שינית?",
        "היה רגע שבו למדת לבקש סליחה או להקשיב אחרת לילדים שלך?",
        "איך היית מתאר את היחסים בינך לבין כל אחד מהילדים — מה מיוחד בכל אחד מהם?",
        "איך השתנתה הזוגיות שלכם עם השנים ועם ההורות?",
        "מהו אחד הזיכרונות הכי יפים שלך כמשפחה?",
        "מה היית רוצה שילדיך יזכרו ממך כשיחשבו על הילדות שלהם?",
        "אם היית יכול לחזור אחורה — יש משהו שהיית עושה אחרת כהורה?",
        "כשאתה מסתכל על המשפחה שלך היום — במה אתה הכי גאה?"
    ],
    "8": [
        "מי היה החבר או החברה הראשונים שאתה זוכר מהילדות?",
        "מה לדעתך יוצר חברות טובה באמת?",
        "תוכל לספר על חברות שנמשכה שנים רבות? מה החזיק אותה?",
        "איך אתה בוחר במי לתת אמון?",
        "היה לך חבר או חברה שהרגשת שהם “כמו משפחה”?",
        "איך שמרת על קשרים לאורך השנים — עם המעברים, השינויים והזמן?",
        "היה ריב או נתק עם חבר קרוב? איך זה הרגיש, ומה קרה אחר כך?",
        "תוכל לספר על מישהו שעזר לך בתקופה קשה?",
        "ומה עם מישהו שאתה עזרת לו — רגע שבו היית שם בשביל אחר?",
        "אילו חוויות משותפות הכי חיזקו את הקשרים שלך עם אחרים?",
        "תוכל לתאר מפגש חברים או בילוי שנחרט לך בזיכרון?",
        "האם יש קבוצה או קהילה שאתה מרגיש חלק ממנה — בבית, בעבודה, בשכונה או בתחביבים?",
        "איך התחושה להיות שייך למקום או לקבוצה?",
        "האם היה שלב בחיים שבו הרגשת לבד או מנותק חברתית? איך יצאת מזה?",
        "מה אתה הכי מעריך באנשים שאתה מוקף בהם?",
        "תוכל לתאר אדם אחד מחייך החברתיים שהשפיע עליך במיוחד?",
        "איך השתנו מערכות היחסים החברתיות שלך לאורך השנים?",
        "מה היה תפקידך בחבורה — היית המקשיב, המצחיק, המארגן?",
        "איך חוגגים אצלך עם חברים — יום הולדת, חג, ערב רגיל?",
        "האם אתה מרגיש שיש לך מעגל תמיכה — אנשים שאתה יכול לסמוך עליהם באמת?",
        "תוכל לספר על מפגש לא צפוי עם אדם מהעבר?",
        "מה למדת מחברות שנגמרה — על עצמך או על החיים?",
        "האם היו אנשים שהפכו מחברים לשותפים לעבודה, או להפך?",
        "מה גורם לך להרגיש שייך — מקום, אנשים, ערכים?",
        "אם היית צריך לבחור אדם אחד שילווה אותך לכל החיים — מי זה היה ולמה?"
    ],
    "9": [
        "אילו דברים אהבת לעשות בזמנך הפנוי כשהיית צעיר?",
        "מהו התחביב הראשון שאתה זוכר שהיה ממש “שלך”?",
        "איך התחלת לעסוק בו — במקרה, ממישהו שלימד אותך, או פשוט סקרנות?",
        "מה גורם לך תחושת רוגע או שמחה אמיתית?",
        "אילו תחביבים מלווים אותך עד היום?",
        "האם אתה טיפוס של יצירה, תנועה, למידה, או אולי הכול יחד?",
        "תוכל לתאר רגע שבו פשוט הרגשת “באזור שלך” — לגמרי נוכח ומאושר?",
        "האם יש פעילות שאתה חולם תמיד לנסות אבל עוד לא הספקת?",
        "אילו חפצים, כלים או פריטים מתקשרים אצלך לתחביבים שלך?",
        "אם היית צריך לבחור יום חופש מושלם — איך הוא היה נראה?",
        "האם אתה נהנה יותר מפעילויות לבד או בחברה?",
        "היה לך תקופה שבה גילית תחביב חדש לגמרי? איך זה קרה?",
        "מה אתה אוהב לעשות כשיש לך זמן לעצמך בלבד?",
        "תוכל לספר על מקום שאתה אוהב ללכת אליו כדי “לנקות את הראש”?",
        "האם יש פעילות שאתה משתף בה גם את המשפחה או החברים?",
        "מה המוזיקה, הסרטים או הספרים שאתה חוזר אליהם שוב ושוב?",
        "אילו טיולים, נופים או מקומות מרגשים במיוחד עבורך?",
        "האם אתה אוהב ליצור במו ידיך — לבשל, לבנות, לצייר, לכתוב?",
        "היה רגע שבו תחביב הפך למשהו גדול יותר — אולי לעיסוק או שליחות?",
        "אם היית צריך לתאר את עצמך דרך תחביביך — מה הם היו מספרים עליך?",
        "איך אתה אוהב לנוח אחרי יום עמוס?",
        "אילו פעילויות קטנות עושות לך שמח ביומיום?",
        "תוכל לזכור חוויה מצחיקה או מיוחדת שקרתה תוך כדי עיסוק בתחביב שלך?",
        "האם היית רוצה ללמוד משהו חדש היום — תחום, שפה, כלי נגינה, ספורט?",
        "מה בעיניך הזמן הפנוי האידיאלי — שקט, מלא תנועה, או שילוב ביניהם?"
    ],
    "10": [
        "אילו ערכים היית אומר שמלווים אותך כל חייך?",
        "מאיפה למדת את הערכים האלה — מהבית, מהחיים, מהניסיון?",
        "יש משפט, אמירה או כלל שאתה משתדל לחיות לפיו?",
        "מה בעיניך חשוב יותר — כנות, נדיבות, אהבה, אחריות, או משהו אחר?",
        "איך אתה מגדיר מהו “אדם טוב”?",
        "היו רגעים שבהם הערכים שלך עמדו למבחן?",
        "אילו דברים אתה מתקשה לסלוח עליהם — ולאיזה דברים אתה מוכן לוותר בקלות?",
        "האם יש אדם שאתה רואה בו דוגמה לערכים שאתה מעריך?",
        "מה בעיניך הדבר הנכון לעשות כשיש התנגשות בין מה שאתה רוצה למה שאתה מאמין בו?",
        "איך אתה מתמודד עם קונפליקטים מוסריים או מצפוניים?",
        "האם יש עיקרון שאתה משתדל להעביר לילדיך או לנכדיך?",
        "איך אתה מתייחס לדת או לרוחניות — האם יש לזה מקום בחייך?",
        "האם אתה מאמין שיש משהו מעבר למה שאנחנו רואים כאן ועכשיו?",
        "אילו חגים, טקסים או מסורות משמעותיים עבורך — ומדוע?",
        "תוכל לתאר רגע שבו הרגשת חיבור רוחני, גם אם לא דתי?",
        "האם יש ערך שלמדת רק בגיל מאוחר — אחרי שנפלת, חווית, או ראית משהו בעיניים אחרות?",
        "מה אתה חושב שמחזיק משפחה או חברה ביחד — על מה זה נשען?",
        "אילו דברים אתה לא מוכן לוותר עליהם לעולם?",
        "האם היה זמן שבו שינת דעה או אמונה שהייתה לך בעבר?",
        "מה אתה חושב על מושגים כמו גורל, מזל או בחירה חופשית?",
        "איך אתה מתמודד עם טעויות שלך — האם אתה סלחן כלפי עצמך?",
        "מה אתה מרגיש שנותן משמעות לחיים שלך?",
        "אילו ערכים היית רוצה שיזכרו אותך לפיהם?",
        "מה אתה חושב שהעולם שלנו צריך יותר ממנו כיום?",
        "אם היית צריך להעביר מסר אחד לדור הבא — מה הוא היה?"
    ],
    "11": [
        "האם תוכל לספר על תקופה קשה בחיים שלך — ומה עזר לך לעבור אותה?",
        "איך אתה נוטה להתמודד כשמגיעים אתגרים או משברים?",
        "היה רגע שבו הרגשת שאתה מאבד כיוון — ומה עזר לך למצוא אותו מחדש?",
        "האם חווית אובדן משמעותי בחייך? איך התמודדת עם התחושות שאחריו?",
        "מהו הדבר שלמדת על עצמך דווקא מתוך כאב או קושי?",
        "מי היו האנשים שהיו לצידך ברגעים האלה?",
        "היה מישהו שהפתיע אותך בתמיכה שלו?",
        "האם יש משפט, אמונה או מחשבה שעזרה לך “להחזיק מעמד”?",
        "מה עוזר לך למצוא תקווה כשדברים נראים אבודים?",
        "תוכל לתאר רגע שבו הבנת שאתה חזק יותר ממה שחשבת?",
        "האם יש חוויה קשה שהפכה אחר כך להזדמנות לצמיחה?",
        "איך אתה מתמודד עם פרידות — מאנשים, ממקומות, מתקופות בחיים?",
        "היה מקרה שבו היית צריך לסלוח — לעצמך או למישהו אחר?",
        "אילו תובנות קיבלת מתקופות מאתגרות שעברת?",
        "מה למדת על החיים מהמקומות הפחות פשוטים?",
        "האם יש רגע שבו הרגשת שינוי פנימי גדול — כמו “משהו נפל למקום”?",
        "מי או מה נותן לך תחושת יציבות כשאתה מתמודד עם סערה?",
        "איך אתה מדבר עם עצמך ברגעים קשים — באיזה קול פנימי?",
        "האם יש משהו מהעבר שלא סופר או לא נגעת בו עד היום?",
        "איך אתה נפרד מדברים שכבר לא שלך — יחסים, תקופות, חלומות?",
        "האם חווית רגע שבו מישהו הציל אותך, במובן רגשי או ממשי?",
        "מה למדת על חמלה — כלפי עצמך וכלפי אחרים?",
        "תוכל לספר על רגע שבו בחרת להמשיך הלאה למרות הכול?",
        "מה עוזר לך להרגיש שלווה אחרי סערה?",
        "כשאתה מסתכל אחורה — מהו השיעור הכי גדול שהחיים לימדו אותך?"
    ],
    "12": [
        "כשאתה מביט אחורה על חייך — מה אתה רואה קודם כל?",
        "אילו רגעים קטנים אתה הכי מעריך היום, במבט לאחור?",
        "מה בעיניך המשמעות של חיים טובים?",
        "אם היית צריך לבחור שלושה דברים שאתה גאה בהם במיוחד — מה הם?",
        "מה היית אומר לגרסה הצעירה של עצמך, לו היית פוגש אותה היום?",
        "האם יש משהו שהיית רוצה לעשות אחרת — או אולי בכלל לא לשנות?",
        "איזה חולם היית בילדותך — ומה מהחלומות ההם התגשם?",
        "יש חלום שעדיין לא הגשמת, אבל אתה עדיין מאמין בו?",
        "אילו דברים קטנים אתה עוד רוצה לחוות או לנסות?",
        "איך אתה מדמיין את השנים הבאות?",
        "מה גורם לך להרגיש חי באמת?",
        "מה אתה מאחל לעצמך לעתיד?",
        "איך אתה רוצה שיזכרו אותך — כאדם, כהורה, כחבר, כאיש משפחה?",
        "אילו מסרים היית רוצה להשאיר לדורות הבאים במשפחה שלך?",
        "מה למדת על אהבה, על זמן, על החיים עצמם?",
        "האם יש משהו שאתה מרגיש שסגרת איתו מעגל?",
        "על מה אתה רוצה להמשיך ללמוד, להתפתח או להתעניין?",
        "מה גורם לך עדיין להתרגש או להתלהב כמו פעם?",
        "האם יש דבר שתרצה לספר ולא יצא לך אף פעם — משהו שחשוב לך שיישמע?",
        "אם היית כותב מכתב לעתיד שלך — מה היית כותב בו?",
        "מה אתה מאחל לעולם של הדור הבא?",
        "אילו הרגלים או ערכים היית רוצה שיעברו הלאה מהמשפחה שלך?",
        "איך אתה מתמודד עם הזמן שעובר — עם שינויים, זיכרונות, געגועים?",
        "אם היית יכול לתמצת את כל מה שלמדת במשפט אחד — מה הוא היה?",
        "כשאתה חושב על סיפור חייך, מה הכותרת שהיית נותן לו?"
    ],
    },
    "en": {
        "1": [
            "What's your name? How old are you? Where were you born?",
            "Where were you born, and what do you remember about the place where you began your life?",
            "What's the story behind your name—who chose it and why?",
            "What's your first memory as a child?",
            "What was the house you grew up in like—the smells, sounds, sensations?",
            "Who were the people who lived with you at home, and how did you get along?",
            "Which holidays were most meaningful in your home, and how did you celebrate them?",
            "What was your favorite food in childhood, and who made it?",
            "Can you tell a funny or embarrassing story that happened to you as a child?",
            "Who was the person closest to you in childhood—and why?",
            "What games or activities did you love to do when you were little?",
            "Who was your best friend in childhood, and what did you love doing together?",
            "What songs, stories, or melodies do you remember from home?",
            "What did you learn from your mother—not necessarily in words, but from her behavior?",
            "And what did you learn from your father?",
            "What beliefs, values, or \"fixed\" phrases were heard in your home?",
            "Describe a family moment you remember as especially warm?",
            "Was there someone in the family everyone laughed at, or who was the \"clown\" of the family?",
            "What family traditions or habits did you love most?",
            "Were there family stories passed down through generations—about migration, immigration, love, or survival?",
            "What was the neighborhood or village you grew up in like? Who were the people around you?",
            "How did the family cope with difficult or challenging moments?",
            "What smell or taste immediately brings you back home?",
            "If you had to choose one picture that represents the home you grew up in—what picture would that be?",
            "What do you think you inherited from your family—a trait, habit, or approach to life?",
            "If you could talk to one of your family ancestors, who would it be and what would you ask them?"
        ],
        "2": [
            "Where did you spend most of your time as a child? At home, outside, with friends, in nature?",
            "Who was your best friend in childhood, and what did you love doing together?",
            "What game or toy was your favorite?",
            "What food or treat made you happiest as a child?",
            "Did you have a secret or special place you loved being alone?",
            "What smell or taste immediately reminds you of your childhood?",
            "What's one of your first memories from kindergarten or school?",
            "Which teacher or caregiver influenced you especially—and why?",
            "How would you describe yourself as a child? Shy, curious, mischievous, calm...?",
            "What made you laugh hardest when you were little?",
            "Can you tell a funny or strange story that happened to you in childhood?",
            "What were you afraid of when you were little—and what helped you calm down?",
            "What made you feel protected or loved?",
            "Were there pets at home? What do you remember about them?",
            "What hobbies or activities did you love doing alone?",
            "What were your birthdays like? Who came, and how did you celebrate?",
            "What was your childhood dream—what did you want to be when you grew up?",
            "Was there a period in your childhood you remember especially fondly? Why that one?",
            "Can you describe a typical day in your childhood—from morning to evening?",
            "What happened when you did something mischievous or didn't listen to your parents?",
            "Which vacations, trips, or family experiences do you remember especially?",
            "If you could go back to one day in your childhood—which day would you return to?",
            "Who was the hero or character you admired in childhood—from a movie, book, or real life?",
            "What did you learn about yourself as a child that stays with you today?",
            "If you had to describe your childhood in one word—what word would that be?"
        ],
        "3": [
            "At what age do you feel your \"teenage years\" really began?",
            "What was that period like for you—were you more rebellious, curious, romantic, shy?",
            "Can you describe what the neighborhood, city, or school looked like in those years?",
            "Who were your close friends in adolescence? What connected you?",
            "What music did you listen to then—and which song immediately takes you back to that time?",
            "Did you have a regular place where you met—a rooftop, garden, mall, beach?",
            "How did you dress then? Were there styles or trends identified with you?",
            "What made you feel like you \"belonged\"?",
            "When did you first feel different—in thought, taste, or how you see the world?",
            "What hobbies or activities filled your time then?",
            "Can you tell about first love—how it started, how it ended, what you learned from it?",
            "Who was your role model during that period?",
            "How were your relationships with your parents in those years?",
            "Did you feel freedom or restrictions at home / at school?",
            "When did you first stand up for yourself or do something \"against the rules\"?",
            "What was your dream then about the future?",
            "If you had to choose one moment that symbolizes your teenage years—what is it?",
            "How did you experience high school—did you study willingly, get bored, search for yourself?",
            "Did you have a teacher or mentor who stayed especially in your memory?",
            "What was the period of final exams or graduation like for you?",
            "Which vacations, trips, or group experiences do you remember from that period?",
            "If you could talk to yourself at age 16 today, what would you say?",
            "What was your first friendship like—what did you learn from it about yourself?",
            "What would you want your children or grandchildren to know about you at that age?",
            "In one word, how would you describe your teenage years?"
        ],
        "4": [
            "When did you first feel love? How did it feel?",
            "Do you remember the first time you really fell in love? How did that relationship begin?",
            "What attracted you to the person you first loved?",
            "How would you describe yourself in relationships at a young age?",
            "What did you learn about yourself from your first love?",
            "What was courtship like for you—what was considered \"romantic\"?",
            "Can you tell about a funny or embarrassing moment that happened in one of your loves?",
            "How did you know you met someone you wanted to share your life with?",
            "What made you feel security and trust in a romantic relationship?",
            "What qualities did you seek or value in a partner?",
            "What were the small moments of love like—not the grand gestures, but everyday life?",
            "Can you describe a moment when you felt truly loved?",
            "How did you deal with disagreements or difficult periods in your relationship?",
            "What did you learn about communication and trust from your relationships?",
            "What values were important to you within a relationship?",
            "If there was a period of separation or heartbreak—what helped you get through it?",
            "How has the meaning of love changed in your eyes over the years?",
            "Which people or couples in your life were models of good love for you?",
            "How did you feel on the day you got married (if you did)? What do you remember from the moments around it?",
            "What song, place, or smell reminds you of great love?",
            "Do you think there's such a thing as \"one true love\"?",
            "What makes a relationship last over time, in your opinion?",
            "If you had to advise your grandchild about love—what would you say?",
            "What excites you most in your relationship today?",
            "What have you learned about love—in the deepest sense of the word?"
        ],
        "5": [
            "How did you feel when you faced this stage—military service, national service, or starting studies?",
            "How did you choose your path—was it a dream, a rational decision, or just what happened?",
            "Can you describe your first day in the military or at school? What goes through your head when you remember it?",
            "Who were the first people you met there, and did you stay in touch?",
            "What traits of yours stood out especially during that period?",
            "Was there someone you saw as a commander, guide, or life teacher? What did you learn from them?",
            "Can you tell about a particularly meaningful experience from service or studies?",
            "Was there a moment when you felt real pride in yourself?",
            "And what about a difficult moment—how did you deal with it?",
            "How did the way you saw yourself change during that period?",
            "Was this a period of freedom and independence or challenges and pressures?",
            "What friendships formed there, and what was special about them?",
            "Can you describe a funny or unforgettable situation from service or campus?",
            "If you studied a profession—why that one, and do you think it was the right choice?",
            "Were there people who opened doors for you or believed in you especially?",
            "What were your days like—routine, tasks, studies, vacations?",
            "What was the most challenging thing for you during that period?",
            "Was there a moment when you felt you were truly maturing?",
            "How did you keep in touch with home and family during that period?",
            "Did you miss something from your life before?",
            "Can you describe a specific place from service or studies that's etched in your memory?",
            "What did you learn there about people—about friendship, trust, cooperation?",
            "Were there dreams or plans that grew during those years?",
            "How did that period contribute to shaping who you are today?",
            "If you could meet yourself on the day of discharge or graduation—what would you say?"
        ],
        "6": [
            "What was your first job or occupation? How did you get into it?",
            "How did you feel on your first day at work?",
            "Who was the first person who taught you \"how things really work\"?",
            "What made you choose the profession or field you worked in most of your life?",
            "What values did you try to bring with you to work?",
            "Was there a moment when you felt you were \"in the right place\"?",
            "And what about a moment when you felt stuck or disappointed?",
            "What did you learn about yourself through work?",
            "How would you describe your relationships with colleagues, employees, or managers?",
            "Can you tell about a significant professional decision you made—and why?",
            "Was there a project, task, or achievement you remember with special pride?",
            "If you had to choose one trait that helped you succeed—what is it?",
            "How did you manage to maintain balance between work, home, and personal life?",
            "Were there moments when you considered changing direction? What made you stay or move?",
            "Can you describe someone at work who influenced you especially?",
            "How did you deal with stress or difficult situations at work?",
            "What gave you a real sense of meaning in what you did?",
            "Was there a period when you worked especially hard, and what did you learn from it?",
            "If you managed people—what did you learn about leadership and working with others?",
            "What lessons would you want to pass on to the younger generation about career and professional choices?",
            "How would you describe yourself as a worker or team member?",
            "What was the moment when you felt most valued at work?",
            "And what was the moment when you had to be strong or stand up for yourself?",
            "If you could go back—would you choose the same path?",
            "How would you want your work to be remembered—what legacy did you leave?"
        ],
        "7": [
            "Did you always want to be a parent?",
            "Do you remember the moment you became a parent? How did you feel that day?",
            "How did you choose the names for your children? Is there a special story behind them?",
            "What changed in your life from the moment the children were born?",
            "How would you describe yourself as a parent at the beginning?",
            "What was the thing that scared you most about parenting—and what was the most exciting?",
            "What's a strong childhood memory from when the children were little?",
            "What everyday family moments do you remember with love?",
            "Was there a ritual, tradition, or family habit that was important to maintain at home?",
            "What was your routine like as a family?",
            "What did you learn from your children—perhaps something you didn't expect to learn?",
            "Was there a moment when you understood you were truly a \"parent\"?",
            "How did you deal with challenges or difficulties—health, financial, or emotional?",
            "Can you tell about a moment when you felt real pride in your children?",
            "And what about a moment of worry or great fear?",
            "How did you divide responsibilities at home—who did what, and how did it work?",
            "What values did you try to pass on to your children?",
            "What was dinner time like at your house—what did you talk about, what was the atmosphere?",
            "What habits or customs from your home did you try to preserve—and which did you change?",
            "Was there a moment when you learned to apologize or listen differently to your children?",
            "How would you describe your relationship with each of your children—what's special about each?",
            "How did your relationship change over the years with parenting?",
            "What's one of your most beautiful memories as a family?",
            "What would you want your children to remember about you when they think of their childhood?",
            "If you could go back—is there something you would do differently as a parent?",
            "When you look at your family today—what are you most proud of?"
        ],
        "8": [
            "Who was the first friend you remember from childhood?",
            "What do you think creates a truly good friendship?",
            "Can you tell about a friendship that lasted many years? What kept it going?",
            "How do you choose who to trust?",
            "Did you have a friend who felt like \"family\"?",
            "How did you maintain connections over the years—with moves, changes, and time?",
            "Was there a fight or break with a close friend? How did it feel, and what happened after?",
            "Can you tell about someone who helped you during a difficult time?",
            "And what about someone you helped—a moment when you were there for another?",
            "What shared experiences most strengthened your connections with others?",
            "Can you describe a friend gathering or outing that's etched in your memory?",
            "Is there a group or community you feel part of—at home, work, neighborhood, or hobbies?",
            "What does it feel like to belong to a place or group?",
            "Was there a stage in life when you felt alone or socially disconnected? How did you get out of it?",
            "What do you most value in the people around you?",
            "Can you describe one person from your social life who influenced you especially?",
            "How did your social relationships change over the years?",
            "What was your role in the group—were you the listener, the funny one, the organizer?",
            "How do you celebrate with friends—birthday, holiday, regular evening?",
            "Do you feel you have a support circle—people you can really rely on?",
            "Can you tell about an unexpected meeting with someone from the past?",
            "What did you learn from a friendship that ended—about yourself or life?",
            "Were there people who went from friends to work partners, or vice versa?",
            "What makes you feel you belong—place, people, values?",
            "If you had to choose one person to accompany you for life—who would it be and why?"
        ],
        "9": [
            "What things did you love doing in your free time when you were young?",
            "What's the first hobby you remember that was really \"yours\"?",
            "How did you start doing it—by chance, from someone who taught you, or just curiosity?",
            "What gives you a feeling of calm or real joy?",
            "What hobbies have stayed with you until today?",
            "Are you a type who creates, moves, learns, or maybe all together?",
            "Can you describe a moment when you simply felt \"in your zone\"—completely present and happy?",
            "Is there an activity you've always dreamed of trying but haven't yet?",
            "What objects, tools, or items are connected to your hobbies?",
            "If you had to choose a perfect day off—what would it look like?",
            "Do you enjoy activities alone or in company more?",
            "Was there a period when you discovered a completely new hobby? How did it happen?",
            "What do you love doing when you have time just for yourself?",
            "Can you tell about a place you love going to \"clear your head\"?",
            "Is there an activity you share with family or friends?",
            "What music, movies, or books do you return to again and again?",
            "Which trips, landscapes, or places are especially exciting for you?",
            "Do you love creating with your own hands—cooking, building, painting, writing?",
            "Was there a moment when a hobby became something bigger—perhaps an occupation or calling?",
            "If you had to describe yourself through your hobbies—what would they say about you?",
            "How do you like to rest after a busy day?",
            "What small activities make you happy in daily life?",
            "Can you remember a funny or special experience that happened while doing your hobby?",
            "Would you want to learn something new today—a field, language, instrument, sport?",
            "What's ideal free time in your eyes—quiet, full of movement, or a combination?"
        ],
        "10": [
            "What values would you say have accompanied you all your life?",
            "Where did you learn those values—from home, life, experience?",
            "Is there a phrase, saying, or rule you try to live by?",
            "What's more important in your eyes—honesty, generosity, love, responsibility, or something else?",
            "How do you define what a \"good person\" is?",
            "Were there moments when your values were tested?",
            "What things do you find hard to forgive—and what are you willing to let go easily?",
            "Is there a person you see as an example of values you appreciate?",
            "What's the right thing to do in your eyes when there's a conflict between what you want and what you believe?",
            "How do you deal with moral or conscience conflicts?",
            "Is there a principle you try to pass on to your children or grandchildren?",
            "How do you relate to religion or spirituality—does it have a place in your life?",
            "Do you believe there's something beyond what we see here and now?",
            "Which holidays, ceremonies, or traditions are meaningful to you—and why?",
            "Can you describe a moment when you felt a spiritual connection, even if not religious?",
            "Is there a value you learned only later in life—after falling, experiencing, or seeing something with different eyes?",
            "What do you think holds a family or society together—what does it rest on?",
            "What things are you not willing to give up ever?",
            "Was there a time when you changed an opinion or belief you had before?",
            "What do you think about concepts like fate, luck, or free choice?",
            "How do you deal with your mistakes—are you forgiving toward yourself?",
            "What do you feel gives meaning to your life?",
            "What values would you want to be remembered by?",
            "What do you think our world needs more of today?",
            "If you had to pass on one message to the next generation—what would it be?"
        ],
        "11": [
            "Can you tell about a difficult period in your life—and what helped you get through it?",
            "How do you tend to cope when challenges or crises come?",
            "Was there a moment when you felt you were losing direction—and what helped you find it again?",
            "Did you experience a significant loss in your life? How did you deal with the feelings after it?",
            "What's something you learned about yourself specifically from pain or difficulty?",
            "Who were the people who were by your side in those moments?",
            "Was there someone who surprised you with their support?",
            "Is there a phrase, belief, or thought that helped you \"hold on\"?",
            "What helps you find hope when things seem lost?",
            "Can you describe a moment when you understood you were stronger than you thought?",
            "Is there a difficult experience that later became an opportunity for growth?",
            "How do you deal with separations—from people, places, periods in life?",
            "Was there a case when you had to forgive—yourself or someone else?",
            "What insights did you gain from challenging periods you went through?",
            "What did you learn about life from the less simple places?",
            "Is there a moment when you felt a big internal change—like \"something fell into place\"?",
            "Who or what gives you a sense of stability when dealing with a storm?",
            "How do you talk to yourself in difficult moments—in what inner voice?",
            "Is there something from the past that hasn't been told or touched until today?",
            "How do you part from things that are no longer yours—relationships, periods, dreams?",
            "Did you experience a moment when someone saved you, emotionally or literally?",
            "What did you learn about compassion—toward yourself and others?",
            "Can you tell about a moment when you chose to move forward despite everything?",
            "What helps you feel peace after a storm?",
            "When you look back—what's the biggest lesson life taught you?"
        ],
        "12": [
            "When you look back on your life—what do you see first?",
            "What small moments do you most appreciate today, looking back?",
            "What's the meaning of a good life in your eyes?",
            "If you had to choose three things you're especially proud of—what are they?",
            "What would you say to the younger version of yourself if you met them today?",
            "Is there something you'd want to do differently—or maybe not change at all?",
            "What dreamer were you in childhood—and which of those dreams came true?",
            "Is there a dream you haven't fulfilled yet, but still believe in?",
            "What small things do you still want to experience or try?",
            "How do you imagine the coming years?",
            "What makes you feel truly alive?",
            "What do you wish for yourself for the future?",
            "How do you want to be remembered—as a person, parent, friend, family member?",
            "What messages would you want to leave for future generations in your family?",
            "What have you learned about love, time, life itself?",
            "Is there something you feel you've closed a circle with?",
            "What do you want to continue learning, developing, or being interested in?",
            "What still excites or thrills you like before?",
            "Is there something you'd want to tell but never got to—something important for you to be heard?",
            "If you wrote a letter to your future—what would you write?",
            "What do you wish for the world of the next generation?",
            "What habits or values would you want passed on from your family?",
            "How do you deal with time passing—with changes, memories, longing?",
            "If you could summarize everything you've learned in one sentence—what would it be?",
            "When you think about your life story, what title would you give it?"
        ],
    },
}



# ANSWERS dictionary removed - now using database

class ChapterOut(BaseModel):
    id: str
    title: str

class QuestionOut(BaseModel):
    id: str
    chapter_id: str
    text: str
    order: int

class UpsertQuestionsIn(BaseModel):
    chapter_id: str
    questions: List[str]

class AnswerIn(BaseModel):
    person_id: str
    chapter_id: str
    question_id: str
    text: str
    audio_url: Optional[str] = None

class StoryChapterIn(BaseModel):
    person_id: str
    chapter_id: str
    style_guide: Optional[str] = None
    context_summary: Optional[str] = None

class StoryCompileIn(BaseModel):
    person_id: str
    style_guide: Optional[str] = None

class UserOut(BaseModel):
    id: str
    person_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    picture: Optional[str] = None
    oauth_provider: Optional[str] = None
    can_use_llm: bool = False
    language: str = "he"  # Default to Hebrew
    
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class UpdateLanguageIn(BaseModel):
    language: str  # "he" or "en"

class UpdateLLMPermissionIn(BaseModel):
    user_id: Optional[str] = None  # UUID as string
    person_id: Optional[str] = None
    email: Optional[str] = None
    can_use_llm: bool

def normalize_chapter_id(chapter_id: str, language: str = "he") -> str:
    """
    Convert a simple chapter ID (e.g., "1") to the database format (e.g., "1-he").
    If the chapter_id already includes language (e.g., "1-he"), return it as-is.
    """
    if "-" in chapter_id and chapter_id.split("-")[-1] in ["he", "en"]:
        # Already in the correct format
        return chapter_id
    # Convert simple ID to database format
    return f"{chapter_id}-{language}"


def ensure_chapter(ch_id: str, db: Session, language: Optional[str] = None):
    """Ensure a chapter exists in the database."""
    # Normalize chapter ID if needed
    if language:
        normalized_id = normalize_chapter_id(ch_id, language)
        chapter = db.query(Chapter).filter(Chapter.id == normalized_id).first()
    else:
        # Try both languages if language not specified
        chapter = db.query(Chapter).filter(Chapter.id == ch_id).first()
        if not chapter and "-" not in ch_id:
            # Try with Hebrew first, then English
            for lang in ["he", "en"]:
                normalized_id = normalize_chapter_id(ch_id, lang)
                chapter = db.query(Chapter).filter(Chapter.id == normalized_id).first()
                if chapter:
                    break
    if not chapter:
        raise HTTPException(status_code=404, detail=f"Chapter {ch_id} not found")
    return chapter


def get_or_create_user(person_id: str, db: Session) -> User:
    """Get or create a user by person_id (legacy function for backward compatibility)."""
    user = db.query(User).filter(User.person_id == person_id).first()
    if not user:
        user = User(person_id=person_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_question_text(question_id: str, language: str = "he") -> Optional[str]:
    """
    Get the question text from question_id.
    
    Args:
        question_id: Question ID in format "chapter-order" (e.g., "1-01")
        language: Language code ("he" or "en")
        
    Returns:
        Question text or None if not found
    """
    try:
        parts = question_id.split("-")
        if len(parts) != 2:
            return None
        
        chapter_id = parts[0]
        order = int(parts[1])
        
        lang = language if language in ["he", "en"] else "he"
        questions = RAW_QUESTIONS.get(lang, {}).get(chapter_id, [])
        if 1 <= order <= len(questions):
            return questions[order - 1].strip()
    except (ValueError, IndexError):
        pass
    
    return None


def verify_llm_permission(user: User) -> None:
    """
    Verify that the user has permission to make LLM API calls.
    
    Args:
        user: User object to check
        
    Raises:
        HTTPException: If user doesn't have LLM permission
    """
    if not user.can_use_llm:
        raise HTTPException(
            status_code=403,
            detail="LLM API access denied. You don't have permission to use LLM features. Please contact support to enable this feature."
        )


# ==================== Authentication Routes ====================

@app.get("/api/auth/google/login")
async def google_login(language: Optional[str] = "he"):
    """Initiate Google OAuth login flow."""
    settings = get_settings()
    
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        )
    
    # Validate language parameter
    if language not in ["he", "en"]:
        language = "en"
    
    # Google OAuth2 authorization URL
    # Note: redirect_uri should match what's configured in Google Cloud Console
    redirect_uri = f"{settings.BACKEND_URL}/api/auth/google/callback"
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.GOOGLE_CLIENT_ID}&"
        f"redirect_uri={redirect_uri}&"
        "response_type=code&"
        "scope=openid email profile&"
        "access_type=offline&"
        "prompt=consent&"
        f"state={language}"  # Pass language as state parameter
    )
    
    return RedirectResponse(url=google_auth_url)


@app.get("/api/auth/google/callback")
async def google_callback(
    code: str,
    state: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Handle Google OAuth callback and create/login user."""
    settings = get_settings()
    
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth not configured"
        )
    
    # Extract language from state parameter (default to Hebrew)
    language = state if state in ["he", "en"] else "he"
    
    # Use backend URL for callback (must match Google Cloud Console configuration)
    redirect_uri = f"{settings.BACKEND_URL}/api/auth/google/callback"
    
    # Exchange authorization code for access token
    async with get_google_oauth_client() as client:
        token_response = await client.fetch_token(
            "https://oauth2.googleapis.com/token",
            code=code,
            redirect_uri=redirect_uri,
        )
        
        access_token = token_response.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=400,
                detail="Failed to obtain access token"
            )
        
        # Get user info from Google
        user_info = await get_google_user_info(access_token)
    
    # Get or create user
    user = get_or_create_user_from_oauth(
        oauth_provider="google",
        oauth_id=user_info.get("id"),
        email=user_info.get("email"),
        name=user_info.get("name"),
        picture=user_info.get("picture"),
        db=db,
    )
    
    # Set language preference if not already set (for existing users) or always for new logins
    # We update language on each login to respect user's current preference
    user.language = language
    db.commit()
    db.refresh(user)
    
    # Create JWT token
    access_token_jwt = create_access_token(data={"sub": str(user.id)})
    
    # Redirect to frontend with token
    frontend_url = settings.FRONTEND_URL
    token_param = urlencode({"token": access_token_jwt})
    return RedirectResponse(url=f"{frontend_url}/auth/callback?{token_param}")


@app.get("/api/auth/me", response_model=UserOut)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user information."""
    return UserOut(
        id=str(current_user.id),
        person_id=current_user.person_id,
        name=current_user.name,
        email=current_user.email,
        picture=current_user.picture,
        oauth_provider=current_user.oauth_provider,
        can_use_llm=current_user.can_use_llm,
        language=current_user.language or "he",
    )


@app.post("/api/auth/logout")
async def logout():
    """Logout endpoint (client should remove token)."""
    return {"message": "Logged out successfully"}


@app.put("/api/auth/language", response_model=UserOut)
async def update_language(
    payload: UpdateLanguageIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's language preference."""
    if payload.language not in ["he", "en"]:
        raise HTTPException(
            status_code=400,
            detail="Language must be 'he' (Hebrew) or 'en' (English)"
        )
    
    current_user.language = payload.language
    db.commit()
    db.refresh(current_user)
    
    return UserOut(
        id=str(current_user.id),
        person_id=current_user.person_id,
        name=current_user.name,
        email=current_user.email,
        picture=current_user.picture,
        oauth_provider=current_user.oauth_provider,
        can_use_llm=current_user.can_use_llm,
        language=current_user.language,
    )


@app.post("/api/admin/llm-permission")
async def update_llm_permission(
    payload: UpdateLLMPermissionIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update LLM permission for a user.
    
    Note: In production, you should add admin role checking here.
    For now, any authenticated user can grant/revoke permissions.
    """
    # Find the target user
    user = None
    
    if payload.user_id:
        try:
            user = db.query(User).filter(User.id == UUID(payload.user_id)).first()
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail="Invalid user_id format"
            )
    elif payload.person_id:
        user = db.query(User).filter(User.person_id == payload.person_id).first()
    elif payload.email:
        user = db.query(User).filter(User.email == payload.email).first()
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide one of: user_id, person_id, or email"
        )
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    # Update permission
    user.can_use_llm = payload.can_use_llm
    db.commit()
    db.refresh(user)
    
    return {
        "message": f"LLM permission {'granted' if payload.can_use_llm else 'revoked'} successfully",
        "user": {
            "id": str(user.id),
            "person_id": user.person_id,
            "email": user.email,
            "can_use_llm": user.can_use_llm
        }
    }


# ==================== API Routes ====================

@app.get("/api/chapters", response_model=List[ChapterOut])
async def list_chapters(
    language: Optional[str] = None,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """List all available chapters in the specified language."""
    # Use language from parameter, user preference, or default to Hebrew
    if language and language in ["he", "en"]:
        lang = language
    elif current_user and current_user.language:
        lang = current_user.language
    else:
        lang = "he"
    
    chapters = db.query(Chapter).filter(Chapter.language == lang).order_by(Chapter.order).all()
    # Return simple chapter IDs (e.g., "1", "2") instead of database format ("1-he", "2-he")
    # Extract the numeric part before the language suffix
    return [{"id": ch.id.split("-")[0] if "-" in ch.id and ch.id.split("-")[-1] in ["he", "en"] else ch.id, "title": ch.title} for ch in chapters]

@app.get("/api/questions", response_model=List[QuestionOut])
async def get_questions(
    chapter: str,
    language: Optional[str] = None,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """Get questions for a specific chapter in the specified language."""
    # Use language from parameter, user preference, or default to Hebrew
    if language and language in ["he", "en"]:
        lang = language
    elif current_user and current_user.language:
        lang = current_user.language
    else:
        lang = "he"
    
    # Normalize chapter ID to database format
    normalized_chapter_id = normalize_chapter_id(chapter, lang)
    
    # Verify chapter exists in the requested language
    chapter_obj = db.query(Chapter).filter(Chapter.id == normalized_chapter_id).first()
    if not chapter_obj:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter} not found for language {lang}")
    
    # Get questions for the specified language (use simple chapter ID for RAW_QUESTIONS lookup)
    simple_chapter_id = chapter.split("-")[0] if "-" in chapter and chapter.split("-")[-1] in ["he", "en"] else chapter
    raw = RAW_QUESTIONS.get(lang, {}).get(simple_chapter_id, [])
    items = [
        {"id": f"{simple_chapter_id}-{i:02d}", "chapter_id": chapter, "text": q.strip(), "order": i}
        for i, q in enumerate(raw, start=1)
    ]
    return items

@app.post("/api/questions", response_model=List[QuestionOut])
def upsert_questions(payload: UpsertQuestionsIn, db: Session = Depends(get_db)):
    """Upsert questions for a chapter."""
    ensure_chapter(payload.chapter_id, db)
    items = []
    for i, qtext in enumerate(payload.questions, start=1):
        qid = f"{payload.chapter_id}-{i:02d}"
        items.append({
            "id": qid,
            "chapter_id": payload.chapter_id,
            "text": (qtext or "").strip(),
            "order": i,
        })
    return items


@app.post("/api/answers")
def add_answer(
    ans: AnswerIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add or update an answer to a question (upsert)."""
    # Use authenticated user or fallback to person_id (for backward compatibility)
    if ans.person_id and ans.person_id != current_user.person_id:
        # If person_id is provided and different, use it (backward compatibility)
        user = get_or_create_user(ans.person_id, db)
    else:
        user = current_user
    
    # Normalize chapter_id based on user's language
    lang = user.language or "he"
    normalized_chapter_id = normalize_chapter_id(ans.chapter_id, lang)
    ensure_chapter(normalized_chapter_id, db, lang)
    
    # Check if answer already exists for this user, chapter, and question
    existing_answer = db.query(Answer).filter(
        Answer.user_id == user.id,
        Answer.chapter_id == normalized_chapter_id,
        Answer.question_id == ans.question_id
    ).first()
    
    if existing_answer:
        # Update existing answer
        existing_answer.text = ans.text
        if ans.audio_url:
            existing_answer.audio_url = ans.audio_url
        db.commit()
        db.refresh(existing_answer)
        return {"ok": True, "answer_id": str(existing_answer.id), "updated": True}
    else:
        # Create new answer
        answer = Answer(
            user_id=user.id,
            chapter_id=normalized_chapter_id,
            question_id=ans.question_id,
            text=ans.text,
            audio_url=ans.audio_url,
        )
        db.add(answer)
        try:
            db.commit()
            db.refresh(answer)
            return {"ok": True, "answer_id": str(answer.id), "updated": False}
        except IntegrityError:
            # Handle race condition: if another request created the answer between our check and insert
            db.rollback()
            # Try to get the existing answer again
            existing_answer = db.query(Answer).filter(
                Answer.user_id == user.id,
                Answer.chapter_id == normalized_chapter_id,
                Answer.question_id == ans.question_id
            ).first()
            if existing_answer:
                # Update it
                existing_answer.text = ans.text
                if ans.audio_url:
                    existing_answer.audio_url = ans.audio_url
                db.commit()
                db.refresh(existing_answer)
                return {"ok": True, "answer_id": str(existing_answer.id), "updated": True}
            else:
                # This shouldn't happen, but handle it anyway
                raise HTTPException(status_code=500, detail="Failed to save answer")

@app.get("/api/answers")
def get_answers(
    chapter: str,
    person_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get answers for a person and chapter."""
    # Use authenticated user or person_id parameter (if provided and matches)
    if person_id:
        user = db.query(User).filter(User.person_id == person_id).first()
        if not user:
            return []
        # Verify it matches current user (security)
        if user.id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You can only access your own answers"
            )
    else:
        user = current_user
    
    # Normalize chapter_id based on user's language
    lang = user.language or "he"
    normalized_chapter_id = normalize_chapter_id(chapter, lang)
    ensure_chapter(normalized_chapter_id, db, lang)
    
    # Get answers
    answers = db.query(Answer).filter(
        Answer.user_id == user.id,
        Answer.chapter_id == normalized_chapter_id
    ).order_by(Answer.created_at).all()
    
    return [
        {
            "id": str(ans.id),
            "question_id": ans.question_id,
            "text": ans.text,
            "audio_url": ans.audio_url,
            "created_at": ans.created_at.isoformat(),
        }
        for ans in answers
    ]

@app.post("/api/story/chapter")
async def story_chapter(
    payload: StoryChapterIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a chapter narrative from answers using LLM."""
    # Use authenticated user or fallback to person_id (for backward compatibility)
    if payload.person_id and payload.person_id != current_user.person_id:
        user = get_or_create_user(payload.person_id, db)
    else:
        user = current_user
    
    # Normalize chapter_id based on user's language
    lang = user.language or "he"
    normalized_chapter_id = normalize_chapter_id(payload.chapter_id, lang)
    ensure_chapter(normalized_chapter_id, db, lang)
    
    # Fetch answers for this chapter
    chapter_answers = db.query(Answer).filter(
        Answer.user_id == user.id,
        Answer.chapter_id == normalized_chapter_id
    ).order_by(Answer.created_at).all()
    
    if not chapter_answers:
        raise HTTPException(
            status_code=400,
            detail=f"No answers found for person {payload.person_id} in chapter {payload.chapter_id}"
        )
    
    # Get current chapter info for ordering (use normalized chapter_id)
    current_chapter = ensure_chapter(normalized_chapter_id, db, lang)
    
    # Get previous chapter summaries for context
    previous_summaries = []
    if not payload.context_summary:
        # Get all previous chapters (with lower order number)
        previous_chapters = db.query(StoryChapter).filter(
            StoryChapter.user_id == user.id,
            StoryChapter.summary.isnot(None)  # Only chapters with summaries
        ).join(Chapter).filter(
            Chapter.order < current_chapter.order
        ).order_by(Chapter.order).all()
        
        # Build context summary from previous chapter summaries
        if previous_chapters:
            previous_summaries = [
                f"פרק {sc.chapter_id} ({sc.chapter.title}): {sc.summary}"
                for sc in previous_chapters
            ]
            context_summary = "\n\n".join(previous_summaries)
        else:
            context_summary = payload.context_summary or "אין תקציר מהפרקים הקודמים."
    else:
        context_summary = payload.context_summary
    
    # Convert answers to facts format
    user_language = user.language or "he"
    facts = [
        {
            "question_id": ans.question_id,
            "question": get_question_text(ans.question_id, user_language) or "",
            "text": ans.text,
            "created_at": ans.created_at.isoformat(),
        }
        for ans in chapter_answers
    ]
    
    # Verify LLM permission before making API calls
    verify_llm_permission(user)
    
    # Generate narrative using LLM
    if llm is None:
        # Fallback if LLM not initialized
        narrative = f"[Stub] Narrative for chapter {payload.chapter_id} based on {len(chapter_answers)} answers. LLM not configured."
        summary = ""
    else:
        try:
            narrative = await llm.agenerate_chapter(
                person_id=payload.person_id,
                chapter_id=payload.chapter_id,
                facts=facts,
                style_guide=payload.style_guide,
                context_summary=context_summary,
            )
            narrative = narrative or f"[Generated] Narrative for chapter {payload.chapter_id}"
            
            # Generate summary from the narrative
            summary = await llm.agenerate_summary(narrative)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate chapter narrative: {str(e)}"
            )
    
    # Save or update story chapter in database (use normalized chapter_id)
    existing = db.query(StoryChapter).filter(
        StoryChapter.user_id == user.id,
        StoryChapter.chapter_id == normalized_chapter_id
    ).first()
    
    if existing:
        existing.narrative = narrative
        existing.summary = summary
        existing.style_guide = payload.style_guide
        existing.context_summary = context_summary
        db.commit()
        db.refresh(existing)
    else:
        story_chapter = StoryChapter(
            user_id=user.id,
            chapter_id=normalized_chapter_id,
            narrative=narrative,
            summary=summary,
            style_guide=payload.style_guide,
            context_summary=context_summary,
        )
        db.add(story_chapter)
        db.commit()
        db.refresh(story_chapter)
    
    return {
        "chapter_id": payload.chapter_id,  # Return original simple ID to frontend
        "narrative": narrative,
        "summary": summary
    }

class StoryChapterOut(BaseModel):
    chapter_id: str
    narrative: str
    summary: Optional[str] = None
    style_guide: Optional[str] = None
    context_summary: Optional[str] = None
    created_at: str
    updated_at: str

@app.get("/api/story/chapter/{chapter_id}", response_model=Optional[StoryChapterOut])
async def get_story_chapter(
    chapter_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a story chapter from the database by chapter_id. Returns null if not found."""
    # Normalize chapter_id based on user's language
    lang = current_user.language or "he"
    normalized_chapter_id = normalize_chapter_id(chapter_id, lang)
    ensure_chapter(normalized_chapter_id, db, lang)
    
    # Get story chapter for current user
    story_chapter = db.query(StoryChapter).filter(
        StoryChapter.user_id == current_user.id,
        StoryChapter.chapter_id == normalized_chapter_id
    ).first()
    
    if not story_chapter:
        # Return null instead of 404 - this is expected when story hasn't been generated yet
        return None
    
    # Return simple chapter_id to frontend (remove language suffix)
    simple_chapter_id = normalized_chapter_id.split("-")[0] if "-" in normalized_chapter_id and normalized_chapter_id.split("-")[-1] in ["he", "en"] else normalized_chapter_id
    
    return {
        "chapter_id": simple_chapter_id,
        "narrative": story_chapter.narrative,
        "summary": story_chapter.summary,
        "style_guide": story_chapter.style_guide,
        "context_summary": story_chapter.context_summary,
        "created_at": story_chapter.created_at.isoformat(),
        "updated_at": story_chapter.updated_at.isoformat(),
    }

@app.post("/api/story/compile")
async def story_compile(
    payload: StoryCompileIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Compile a full book from all chapters using LLM."""
    # Use authenticated user or fallback to person_id (for backward compatibility)
    if payload.person_id and payload.person_id != current_user.person_id:
        user = get_or_create_user(payload.person_id, db)
    else:
        user = current_user
    
    # Get all story chapters for this user
    story_chapters = db.query(StoryChapter).filter(
        StoryChapter.user_id == user.id
    ).join(Chapter).order_by(Chapter.order).all()
    
    if not story_chapters:
        raise HTTPException(
            status_code=400,
            detail=f"No story chapters found for person {payload.person_id}"
        )
    
    # Build chapters list with narratives
    chapters = []
    for story_ch in story_chapters:
        chapters.append({
            "id": story_ch.chapter_id,
            "title": story_ch.chapter.title,
            "narrative": story_ch.narrative,
        })
    
    # Verify LLM permission before making API calls
    verify_llm_permission(user)
    
    # Compile book using LLM
    if llm is None:
        # Fallback if LLM not initialized
        book_text = "[Stub] Full life story book text will appear here. LLM not configured."
    else:
        try:
            book_text = await llm.acompile_book(
                person_id=payload.person_id,
                chapters=chapters,
                style_guide=payload.style_guide,
            )
            book_text = book_text or "[Generated] Full life story book"
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to compile book: {str(e)}"
            )
    
    # Save or update story in database
    existing = db.query(Story).filter(Story.user_id == user.id).first()
    
    if existing:
        existing.book_text = book_text
        existing.style_guide = payload.style_guide
        existing.chapters_used = len(chapters)
        db.commit()
        db.refresh(existing)
    else:
        story = Story(
            user_id=user.id,
            book_text=book_text,
            style_guide=payload.style_guide,
            chapters_used=len(chapters),
        )
        db.add(story)
        db.commit()
        db.refresh(story)
    
    return {
        "compiled": True,
        "book": book_text
    }

@app.get("/api/story/{person_id}")
async def get_story(
    person_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the compiled story for a person by person_id."""
    # Get user
    user = db.query(User).filter(User.person_id == person_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"User not found for person_id {person_id}"
        )
    
    # Verify user can only access their own story
    if user.id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only access your own story"
        )
    
    # Get story from database
    story = db.query(Story).filter(Story.user_id == user.id).first()
    
    if story is None:
        # Fallback to LLM if available
        if llm is not None:
            llm_story = llm.get_compiled_story(person_id)
            if llm_story:
                return {
                    "person_id": person_id,
                    "book": llm_story.get("book_text", ""),
                    "style_guide": llm_story.get("style_guide"),
                    "compiled_at": llm_story.get("compiled_at"),
                    "chapters_used": llm_story.get("chapters_used", 0),
                }
        
        raise HTTPException(
            status_code=404,
            detail=f"No compiled story found for person {person_id}"
        )
    
    return {
        "person_id": person_id,
        "book": story.book_text,
        "style_guide": story.style_guide,
        "compiled_at": story.compiled_at.isoformat(),
        "chapters_used": story.chapters_used,
    }
