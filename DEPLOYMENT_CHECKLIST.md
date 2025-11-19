# ✅ Deployment Checklist

רשימת בדיקה לפני פריסה ל-production

## לפני הפריסה

### Backend
- [ ] כל ה-environment variables מוגדרים
- [ ] `SECRET_KEY` הוא מפתח חזק ואקראי (לא default!)
- [ ] `DATABASE_URL` מצביע ל-PostgreSQL ב-production
- [ ] `BACKEND_URL` מצביע ל-URL הנכון של ה-backend
- [ ] `FRONTEND_URL` מצביע ל-URL הנכון של ה-frontend
- [ ] API keys (OpenAI/Anthropic) מוגדרים
- [ ] Google OAuth credentials מוגדרים
- [ ] ה-backend רץ ומגיב (בדוק ב-`/docs`)

### Frontend
- [ ] `VITE_API_BASE` מצביע ל-URL של ה-backend
- [ ] Build עובר בהצלחה (`npm run build`)
- [ ] אין errors ב-console

### Google OAuth
- [ ] OAuth Client ID נוצר ב-Google Cloud Console
- [ ] Authorized redirect URI תואם ל-`BACKEND_URL/api/auth/google/callback`
- [ ] `GOOGLE_CLIENT_ID` ו-`GOOGLE_CLIENT_SECRET` מוגדרים ב-backend

### Database
- [ ] PostgreSQL service רץ
- [ ] `DATABASE_URL` נכון
- [ ] הטבלאות נוצרו (users, chapters, answers, story_chapters, stories)
- [ ] Chapters seeded (12 chapters)

### Security
- [ ] `.env` לא ב-Git (בדוק ב-.gitignore)
- [ ] API keys לא ב-code
- [ ] `SECRET_KEY` לא default
- [ ] CORS מוגדר נכון (רק frontend URL)

## אחרי הפריסה

### בדיקות
- [ ] Frontend נטען ב-Vercel
- [ ] Backend API נגיש (`/docs` עובד)
- [ ] Google Login עובד
- [ ] Database connection עובד
- [ ] API calls עובדים (list chapters, get questions)
- [ ] LLM calls עובדים (אם יש הרשאה)

### Monitoring
- [ ] Logs נגישים (Railway/Render)
- [ ] Errors נצפים
- [ ] Database connections תקינים

### Performance
- [ ] Response times סבירים
- [ ] No memory leaks
- [ ] Database queries יעילים

## Troubleshooting

אם משהו לא עובד:

1. **CORS Error**
   - בדוק ש-`FRONTEND_URL` נכון ב-backend
   - בדוק ש-CORS middleware מאפשר את ה-frontend URL

2. **Database Error**
   - בדוק ש-`DATABASE_URL` נכון
   - בדוק שה-PostgreSQL service רץ
   - בדוק שה-connection string כולל SSL אם נדרש

3. **OAuth Error**
   - בדוק שה-redirect URI ב-Google Console תואם
   - בדוק ש-`GOOGLE_CLIENT_ID` ו-`GOOGLE_CLIENT_SECRET` נכונים

4. **Environment Variables לא עובדים**
   - ודא שהגדרת ב-platform הנכון
   - ודא שעשית redeploy אחרי הוספת משתנים

5. **Build Fails**
   - בדוק את ה-logs ב-Vercel/Railway
   - ודא ש-dependencies מותקנים נכון

## Post-Deployment

- [ ] הגדר database backups
- [ ] שקול להוסיף monitoring (Sentry, etc.)
- [ ] שקול להוסיף rate limiting
- [ ] עדכן documentation אם צריך
- [ ] שתף את ה-URL עם המשתמשים!

