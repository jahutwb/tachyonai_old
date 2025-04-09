# Global Windsurf Rules for TachyonAI

## 1. Deployment Standards

### Environment Management
- **Production Environment**: Use stable tag releases only (e.g., `v1.0.0`, `v2.1.0`)
- **Staging Environment**: Use release candidate tags (e.g., `v1.0.0-rc.1`)
- **Development Environment**: Use feature branch deployments (e.g., `feature/new-trading-algorithm`)

### Build Configuration
- All deployments must include proper environment variable configuration
- Frontend builds must be optimized for production with minification enabled
- Backend services must log at appropriate levels based on environment

### Database Migrations
- Migrations must be run automatically during deployment
- Backward compatibility must be maintained for at least one previous version
- Database rollback plans must be tested before each production deployment

## 2. Security Requirements

### Authentication
- JWT tokens must expire after 24 hours in production
- API keys must be rotated every 90 days
- Failed login attempts must be rate-limited

### Data Protection
- All trading data must be encrypted at rest and in transit
- Image stimuli data must be properly anonymized
- User session data must be isolated and protected

### Access Control
- Admin routes must implement role-based access control using `UserRoleEnum`
- API endpoints must validate session ownership before data access
- All write operations must be properly authorized

## 3. Performance Criteria

### Response Times
- API endpoints must respond within 100ms (95th percentile)
- Image loading must complete within 200ms
- Trading round calculations must complete within 50ms

### Resource Utilization
- CPU usage must not exceed 70% for more than 5 minutes
- Memory usage must stay below 80% of allocated resources
- Database queries must be optimized with appropriate indexes

### Scalability
- Backend services must be horizontally scalable
- Session pools must handle at least 1000 concurrent users
- Rate limiting must be implemented for all public endpoints

## 4. Development Workflow

### Code Quality
- All code must pass linting with zero errors
- Test coverage must be at least 80% for new features
- Pull requests must include appropriate unit and integration tests

### Feature Development
- Features must be developed in isolated branches
- Each feature must have clear acceptance criteria
- Code review by at least one team member is required before merging

### Documentation
- API changes must be documented with OpenAPI/Swagger
- Database schema changes must be documented in project wiki
- User-facing feature changes must include updated help documentation

## 5. Trading Simulation Standards

### Round Management
- Each trading session must maintain consistent `remaining_pairs` count
- Trading rounds must accurately track `profit_fraction` and `result`
- Session termination must properly update `session_profit_factor`

### Image Stimulus Pool
- Image pools must maintain balance between positive and negative stimuli
- Quasi-genetic algorithm must ensure diversity in stimulus selection
- Stimulus statistics must be accurately tracked for performance analysis

### User Experience
- Trading interface must respond to user actions within 50ms
- Visual feedback must be provided for all user actions
- Session summary data must be displayed in an intuitive format

## 6. Monitoring Requirements

### Error Tracking
- All runtime errors must be logged with appropriate context
- Critical errors must trigger alerts to on-call personnel
- Error rates must be monitored with appropriate thresholds

### Performance Monitoring
- API endpoint performance must be tracked in real-time
- Database query performance must be monitored
- Frontend loading times must be tracked with client-side monitoring

### Business Metrics
- User engagement metrics must be tracked and reported
- Trading session completion rates must be monitored
- Profit factor distributions must be analyzed for algorithm effectiveness

## 7. Compliance and Testing

### Automated Testing
- CI pipeline must include unit, integration, and end-to-end tests
- Visual regression testing must be implemented for UI changes
- Load testing must verify system performance under peak conditions

### Accessibility
- UI must meet WCAG 2.1 AA accessibility standards
- Keyboard navigation must be fully supported
- Screen reader compatibility must be maintained

### Compliance
- User data handling must comply with relevant privacy regulations
- Financial simulations must include appropriate disclaimers
- Terms of service must be clearly presented to users
