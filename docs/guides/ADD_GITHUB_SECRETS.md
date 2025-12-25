# Add GitHub Secrets - Step by Step

## 🔐 Quick Link

**Go directly to:** https://github.com/shreyas-chickerur/investor-mimic-bot/settings/secrets/actions

---

## 📋 Step-by-Step Instructions

### 1. Open GitHub Secrets Page

Click this link: https://github.com/shreyas-chickerur/investor-mimic-bot/settings/secrets/actions

Or navigate manually:
- Go to your repository
- Click "Settings" (top right)
- Click "Secrets and variables" (left sidebar)
- Click "Actions"

### 2. Add Each Secret

Click the green "New repository secret" button and add these **5 secrets** one by one:

---

#### Secret 1: ALPACA_API_KEY
```
Name: ALPACA_API_KEY
Secret: PK7ZJKOYNMMWAULRJGFSBLZL54
```
Click "Add secret"

---

#### Secret 2: ALPACA_SECRET_KEY
```
Name: ALPACA_SECRET_KEY
Secret: 4LtTZQw5wGrXLz7Eu7DGoGEc5uwfzuxbkaWgXFiFtemo
```
Click "Add secret"

---

#### Secret 3: EMAIL_USERNAME
```
Name: EMAIL_USERNAME
Secret: schickerur2020@gmail.com
```
Click "Add secret"

---

#### Secret 4: EMAIL_PASSWORD
```
Name: EMAIL_PASSWORD
Secret: guigmczeokncwpin
```
Click "Add secret"

---

#### Secret 5: EMAIL_TO
```
Name: EMAIL_TO
Secret: schickerur2020@gmail.com
```
Click "Add secret"

---

## ✅ Verify Secrets Added

After adding all 5, you should see them listed on the secrets page:
- ALPACA_API_KEY
- ALPACA_SECRET_KEY
- EMAIL_USERNAME
- EMAIL_PASSWORD
- EMAIL_TO

---

## 🧪 Test the Workflow

Once secrets are added:

1. Go to: https://github.com/shreyas-chickerur/investor-mimic-bot/actions
2. Click "Multi-Strategy Daily Execution" workflow
3. Click "Run workflow" button (top right)
4. Select branch: "main"
5. Click green "Run workflow" button

Watch it run! It should complete successfully.

---

## 📅 Automatic Schedule

After successful test, the workflow will run automatically:
- **Every weekday at 9:00 AM ET**
- No manual action needed
- Check your email for daily summaries

---

## ✅ Done!

Once you've added all 5 secrets and tested the workflow, you're completely set up! 🚀
