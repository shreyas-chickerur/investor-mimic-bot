# Web Dashboard Architecture

Complete frontend platform for InvestorMimic Bot with user management, portfolio tracking, and real-time recommendations.

---

## Tech Stack

### Frontend
- **Framework**: React 18 with Next.js 14 (App Router)
- **Styling**: TailwindCSS + shadcn/ui components
- **Charts**: Recharts for performance visualization
- **State Management**: React Context + SWR for data fetching
- **Authentication**: NextAuth.js with JWT
- **Icons**: Lucide React

### Backend API
- **Framework**: FastAPI (Python)
- **Authentication**: JWT tokens
- **Database**: PostgreSQL (existing)
- **Real-time**: Server-Sent Events (SSE) for live updates
- **API Documentation**: OpenAPI/Swagger

### Deployment
- **Frontend**: Vercel or Netlify
- **Backend**: Existing FastAPI server
- **Database**: Existing PostgreSQL

---

## Features

### 1. User Authentication
- Sign up / Sign in
- Email verification
- Password reset
- Session management
- Role-based access (admin/user)

### 2. Dashboard Home
- Account balance (Alpaca)
- Portfolio value chart
- Today's P&L
- Recent trades
- Quick stats (win rate, Sharpe ratio)

### 3. Portfolio View
- Current holdings table
- Performance by position
- Sector allocation pie chart
- Historical performance line chart
- Export to CSV

### 4. Recommendations
- Real-time buy/sell signals
- Causality flow charts (interactive)
- Signal strength indicators
- Historical accuracy tracking
- One-click trade execution

### 5. Settings
- Profile management
- Alpaca API keys
- Email preferences
- Notification settings
- Risk tolerance
- Trading preferences

### 6. Analytics
- User behavior tracking
- Strategy performance comparison
- A/B testing results
- Aggregate statistics
- Success rate by strategy

### 7. Trade History
- All executed trades
- Pending orders
- Cancelled orders
- Trade details with reasoning
- Performance attribution

---

## Database Schema Extensions

### Users Table
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    role VARCHAR(50) DEFAULT 'user'
);
```

### User Settings Table
```sql
CREATE TABLE user_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    alpaca_api_key_encrypted TEXT,
    alpaca_secret_key_encrypted TEXT,
    risk_tolerance VARCHAR(50) DEFAULT 'moderate',
    email_notifications BOOLEAN DEFAULT TRUE,
    trade_notifications BOOLEAN DEFAULT TRUE,
    max_position_size DECIMAL DEFAULT 0.10,
    auto_execute_trades BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### User Activity Tracking
```sql
CREATE TABLE user_activity (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    activity_type VARCHAR(100),
    activity_data JSONB,
    ip_address VARCHAR(50),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Trade Performance Tracking
```sql
CREATE TABLE trade_performance (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    ticker VARCHAR(10),
    action VARCHAR(10),
    entry_date DATE,
    entry_price DECIMAL,
    exit_date DATE,
    exit_price DECIMAL,
    quantity DECIMAL,
    profit_loss DECIMAL,
    profit_loss_pct DECIMAL,
    strategy_used VARCHAR(100),
    signal_score DECIMAL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### User Sessions
```sql
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    token_hash VARCHAR(255) UNIQUE,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    last_activity TIMESTAMP DEFAULT NOW()
);
```

---

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `POST /api/auth/logout` - Logout user
- `POST /api/auth/refresh` - Refresh token
- `POST /api/auth/verify-email` - Verify email
- `POST /api/auth/reset-password` - Reset password

### Dashboard
- `GET /api/dashboard/summary` - Dashboard overview
- `GET /api/dashboard/portfolio` - Portfolio data
- `GET /api/dashboard/performance` - Performance metrics
- `GET /api/dashboard/recent-trades` - Recent trades

### Portfolio
- `GET /api/portfolio/holdings` - Current holdings
- `GET /api/portfolio/history` - Historical performance
- `GET /api/portfolio/allocation` - Asset allocation
- `GET /api/portfolio/export` - Export data

### Recommendations
- `GET /api/recommendations/current` - Current recommendations
- `GET /api/recommendations/{id}` - Recommendation details
- `GET /api/recommendations/{id}/causality` - Flow chart data
- `POST /api/recommendations/{id}/execute` - Execute trade

### Alpaca Integration
- `GET /api/alpaca/account` - Account info
- `GET /api/alpaca/positions` - Current positions
- `GET /api/alpaca/orders` - Order history
- `POST /api/alpaca/order` - Place order

### Settings
- `GET /api/settings/profile` - User profile
- `PUT /api/settings/profile` - Update profile
- `GET /api/settings/preferences` - User preferences
- `PUT /api/settings/preferences` - Update preferences
- `PUT /api/settings/alpaca-keys` - Update Alpaca keys

### Analytics
- `GET /api/analytics/user-stats` - User statistics
- `GET /api/analytics/strategy-performance` - Strategy metrics
- `GET /api/analytics/aggregate` - Aggregate data (admin)

---

## Frontend Pages

### Public Pages
- `/` - Landing page
- `/login` - Login page
- `/register` - Registration page
- `/forgot-password` - Password reset

### Protected Pages
- `/dashboard` - Main dashboard
- `/portfolio` - Portfolio view
- `/recommendations` - Recommendations list
- `/recommendations/[id]` - Recommendation details
- `/trades` - Trade history
- `/settings` - User settings
- `/settings/profile` - Profile settings
- `/settings/preferences` - Preferences
- `/settings/api-keys` - API key management
- `/analytics` - Personal analytics

### Admin Pages
- `/admin/dashboard` - Admin overview
- `/admin/users` - User management
- `/admin/analytics` - System analytics

---

## Security

### Authentication
- JWT tokens with refresh mechanism
- HTTP-only cookies for tokens
- CSRF protection
- Rate limiting on auth endpoints

### Data Protection
- Alpaca API keys encrypted at rest
- Password hashing with bcrypt
- SQL injection prevention
- XSS protection

### API Security
- CORS configuration
- Request validation
- Authentication middleware
- Role-based access control

---

## Real-time Features

### Server-Sent Events (SSE)
- Live portfolio updates
- Real-time recommendations
- Trade execution notifications
- Price updates

### WebSocket Alternative
- Bidirectional communication
- Lower latency
- Better for high-frequency updates

---

## Performance Optimization

### Frontend
- Code splitting
- Lazy loading
- Image optimization
- Caching strategies

### Backend
- Database query optimization
- Redis caching
- Connection pooling
- Response compression

---

## Monitoring & Analytics

### User Tracking
- Page views
- Feature usage
- Trade execution rate
- Session duration
- Conversion funnel

### Performance Metrics
- API response times
- Error rates
- User engagement
- Strategy success rates

---

## Development Workflow

### Setup
```bash
# Frontend
cd frontend
npm install
npm run dev

# Backend (existing)
cd ..
python3 -m uvicorn api.main:app --reload
```

### Testing
```bash
# Frontend tests
npm run test

# Backend tests
pytest tests/

# E2E tests
npm run test:e2e
```

### Deployment
```bash
# Frontend
npm run build
vercel deploy

# Backend
# Already deployed
```

---

## File Structure

```
investor-mimic-bot/
├── frontend/                 # Next.js application
│   ├── app/                 # App router pages
│   │   ├── (auth)/         # Auth pages
│   │   ├── (dashboard)/    # Protected pages
│   │   └── api/            # API routes
│   ├── components/          # React components
│   │   ├── ui/             # shadcn components
│   │   ├── dashboard/      # Dashboard components
│   │   └── charts/         # Chart components
│   ├── lib/                # Utilities
│   ├── hooks/              # Custom hooks
│   └── public/             # Static assets
├── api/                     # FastAPI backend
│   ├── routes/             # API routes
│   ├── auth/               # Authentication
│   ├── middleware/         # Middleware
│   └── models/             # Pydantic models
└── sql/migrations/         # Database migrations
```

---

## Next Steps

1. Create database schema migrations
2. Build FastAPI authentication system
3. Create API endpoints
4. Initialize Next.js frontend
5. Build authentication pages
6. Create dashboard components
7. Implement real-time features
8. Add analytics tracking
9. Deploy and test

---

## Estimated Timeline

- Database setup: 1 day
- Backend API: 3-4 days
- Frontend setup: 1 day
- Dashboard UI: 3-4 days
- Real-time features: 2 days
- Testing & polish: 2 days

**Total: ~2 weeks for MVP**
