# מדריך פריסה ל-Production (MVP)

מדריך זה מסביר איך לפרוס את האפליקציה ל-production בצורה מהירה וקלה.

## אסטרטגיית פריסה מומלצת

- **Frontend**: Vercel (חינמי, מהיר, קל להגדרה)
- **Backend**: Railway או Render (כולל PostgreSQL, קל להגדרה)
- **Database**: PostgreSQL (כולל ב-Railway/Render)

## שלב 1: הכנת Backend

### אופציה A: Railway (מומלץ - הכי מהיר)

1. **הירשם ל-Railway**: https://railway.app
2. **צור פרויקט חדש**:
   - לחץ על "New Project"
   - בחר "Deploy from GitHub repo" (חבר את ה-repo שלך)
   - או "Empty Project" ואז "Add Service" → "GitHub Repo"

3. **הוסף PostgreSQL**:
   - בפרויקט, לחץ "New" → "Database" → "Add PostgreSQL"
   - Railway יוצר אוטומטית את ה-`DATABASE_URL` כ-environment variable

4. **הגדר Environment Variables**:
   - בפרויקט, לחץ על "Variables"
   - הוסף את המשתנים הבאים:

```bash
# Database (נוצר אוטומטית על ידי Railway)
DATABASE_URL=<נוצר אוטומטית>

# LLM Configuration
PROVIDER=openai  # או anthropic
OPENAI_API_KEY=<המפתח שלך מ-OpenAI>
# או
ANTHROPIC_API_KEY=<המפתח שלך מ-Anthropic>

MODEL_NAME=gpt-4o-mini
TEMPERATURE=0.3
TIMEOUT_SEC=45

# OAuth2 (Google)
GOOGLE_CLIENT_ID=<מזהה הלקוח מ-Google Cloud Console>
GOOGLE_CLIENT_SECRET=<הסוד מ-Google Cloud Console>
SECRET_KEY=<מפתח סודי אקראי - השתמש ב-python -c "import secrets; print(secrets.token_urlsafe(32))">

# URLs (חשוב!)
BACKEND_URL=https://<שם-השירות-שלך>.railway.app
FRONTEND_URL=https://<הדומיין-של-vercel>.vercel.app
```

5. **הגדר את Railway להריץ את ה-Backend**:
   - Railway יזהה אוטומטית שזה Python project
   - אם לא, הוסף `railway.json` (ראה למטה)

6. **הגדר את Start Command**:
   - ב-Settings → Deploy → Start Command:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

### אופציה B: Render

1. **הירשם ל-Render**: https://render.com
2. **צור Web Service**:
   - "New" → "Web Service"
   - חבר את ה-GitHub repo
   - בחר את תיקיית `backend`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

3. **הוסף PostgreSQL**:
   - "New" → "PostgreSQL"
   - העתק את ה-`DATABASE_URL` מה-PostgreSQL service

4. **הגדר Environment Variables** (כמו ב-Railway)

## שלב 2: הכנת Frontend

### פריסה ל-Vercel

1. **הירשם ל-Vercel**: https://vercel.com
2. **חבר את ה-GitHub repo**:
   - לחץ "Add New Project"
   - בחר את ה-repo שלך
   - Root Directory: `frontend`
   - Framework Preset: Vite
   - Build Command: `npm run build`
   - Output Directory: `dist`

3. **הגדר Environment Variables**:
   - ב-Project Settings → Environment Variables:
   ```
   VITE_API_BASE=https://<שם-השירות-שלך>.railway.app
   ```
   (או ה-URL של ה-backend ב-Render)

4. **Deploy**:
   - Vercel יבנה ויפרס אוטומטית
   - תקבל URL כמו: `https://your-app.vercel.app`

## שלב 3: הגדרת Google OAuth

1. **Google Cloud Console**:
   - לך ל: https://console.cloud.google.com
   - צור פרויקט חדש או בחר קיים
   - לך ל "APIs & Services" → "Credentials"
   - לחץ "Create Credentials" → "OAuth client ID"
   - בחר "Web application"
   - הוסף Authorized redirect URIs:
     ```
     https://<backend-url>/api/auth/google/callback
     ```
   - העתק את `Client ID` ו-`Client Secret`

2. **עדכן את Environment Variables**:
   - הוסף את `GOOGLE_CLIENT_ID` ו-`GOOGLE_CLIENT_SECRET` ב-Railway/Render

3. **עדכן את Frontend URL ב-Backend**:
   - ודא ש-`FRONTEND_URL` ב-backend מצביע ל-URL של Vercel

## שלב 4: בדיקות

1. **בדוק את ה-Backend**:
   - לך ל: `https://<backend-url>/docs`
   - אמור לראות את ה-Swagger UI

2. **בדוק את ה-Frontend**:
   - לך ל-URL של Vercel
   - נסה להתחבר עם Google

3. **בדוק את ה-Database**:
   - ב-Railway/Render, פתח את ה-PostgreSQL console
   - ודא שהטבלאות נוצרו (users, chapters, answers, וכו')

## שלב 5: הגדרות נוספות (אופציונלי)

### Custom Domain
- **Vercel**: Settings → Domains → Add Domain
- **Railway**: Settings → Domains → Add Custom Domain

### Monitoring
- **Railway**: כולל monitoring מובנה
- **Render**: כולל logs ו-metrics

### SSL/HTTPS
- Vercel ו-Railway/Render מספקים SSL אוטומטי

## פתרון בעיות נפוצות

### CORS Errors
- ודא ש-`FRONTEND_URL` ב-backend נכון
- ודא ש-CORS middleware ב-`main.py` מאפשר את ה-frontend URL

### Database Connection Errors
- ודא ש-`DATABASE_URL` נכון
- ודא שה-PostgreSQL service רץ
- בדוק שה-connection string כולל SSL אם נדרש

### OAuth Errors
- ודא שה-redirect URI ב-Google Console תואם ל-`BACKEND_URL`
- ודא ש-`FRONTEND_URL` נכון ב-backend

### Environment Variables לא עובדים
- ודא שהגדרת את המשתנים ב-platform הנכון
- ודא שעשית redeploy אחרי הוספת משתנים חדשים

## עלויות (MVP)

- **Vercel**: חינמי (עד 100GB bandwidth)
- **Railway**: $5/חודש (500 שעות) או $20/חודש (unlimited)
- **Render**: חינמי (עם הגבלות) או $7/חודש
- **PostgreSQL**: כלול ב-Railway/Render

**סה"כ MVP**: ~$5-20/חודש

## קישורים שימושיים

- [Railway Docs](https://docs.railway.app)
- [Vercel Docs](https://vercel.com/docs)
- [Render Docs](https://render.com/docs)
- [Google OAuth Setup](https://developers.google.com/identity/protocols/oauth2)

## הערות חשובות

1. **SECRET_KEY**: השתמש במפתח חזק ב-production! אל תשתמש ב-default
2. **API Keys**: אל תעלה API keys ל-GitHub! השתמש ב-environment variables
3. **Database Backups**: הגדר backups אוטומטיים ב-Railway/Render
4. **Rate Limiting**: שקול להוסיף rate limiting ב-production
5. **Error Monitoring**: שקול להוסיף Sentry או שירות דומה

