# 🚀 Quick Start - פריסה מהירה ל-MVP

מדריך קצר לפריסה מהירה (10-15 דקות)

## שלב 1: Backend ב-Railway (5 דקות)

1. הירשם ל-https://railway.app
2. "New Project" → "Deploy from GitHub repo"
3. בחר את ה-repo שלך
4. הוסף PostgreSQL: "New" → "Database" → "Add PostgreSQL"
5. הוסף Environment Variables:
   ```
   PROVIDER=openai
   OPENAI_API_KEY=<המפתח שלך>
   GOOGLE_CLIENT_ID=<מזהה הלקוח>
   GOOGLE_CLIENT_SECRET=<הסוד>
   SECRET_KEY=<מפתח אקראי - רץ: python -c "import secrets; print(secrets.token_urlsafe(32))">
   BACKEND_URL=https://<שם-השירות>.railway.app
   FRONTEND_URL=<נעדכן אחרי Vercel>
   ```
6. ב-Settings → Deploy → Start Command:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
7. העתק את ה-URL של ה-backend (למשל: `https://xxx.railway.app`)

## שלב 2: Frontend ב-Vercel (3 דקות)

1. הירשם ל-https://vercel.com
2. "Add New Project" → בחר את ה-repo
3. הגדר:
   - Root Directory: `frontend`
   - Framework: Vite
   - Build Command: `npm run build`
   - Output Directory: `dist`
4. הוסף Environment Variable:
   ```
   VITE_API_BASE=<ה-URL של Railway מהשלב הקודם>
   ```
5. Deploy!
6. העתק את ה-URL של Vercel (למשל: `https://xxx.vercel.app`)

## שלב 3: עדכון URLs (2 דקות)

1. חזור ל-Railway
2. עדכן את `FRONTEND_URL` ל-URL של Vercel
3. Redeploy (Railway יעשה זאת אוטומטית)

## שלב 4: Google OAuth (5 דקות)

1. לך ל-https://console.cloud.google.com
2. צור OAuth Client ID:
   - "APIs & Services" → "Credentials" → "Create Credentials" → "OAuth client ID"
   - Authorized redirect URI: `https://<railway-url>/api/auth/google/callback`
3. העתק Client ID ו-Client Secret
4. עדכן ב-Railway:
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
5. Redeploy

## ✅ סיימת!

עכשיו האפליקציה שלך ב-production!

- Frontend: `https://xxx.vercel.app`
- Backend API: `https://xxx.railway.app`
- API Docs: `https://xxx.railway.app/docs`

## 🔧 פתרון בעיות מהיר

**CORS Error?**
- ודא ש-`FRONTEND_URL` ב-Railway נכון

**Database Error?**
- ודא שה-PostgreSQL service רץ ב-Railway

**OAuth לא עובד?**
- ודא שה-redirect URI ב-Google Console תואם ל-`BACKEND_URL`

---

📖 למדריך מפורט יותר, ראה [DEPLOYMENT.md](./DEPLOYMENT.md)

