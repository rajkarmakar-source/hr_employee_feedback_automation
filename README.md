# HR Employee Feedback Automation

## Requirements

### Form Types
The system will collect feedback through four distinct forms:
- **Employee Form** (Self-feedback)
- **Manager Form**
- **Client Form**
- **Peer Form** (feedback only gathered; not used in appraisals)

### Feedback Collection Process
- Feedback collection will have a **deadline**
- **HR team follow-ups**: At least 5 regular email follow-ups within the deadline period to encourage submission

### Data Processing & Scoring
- All form responses are collected into a **final data sheet**
- **Average score calculation**: For each form, calculate the average of all answers
- **Score Weightage**:
  - Self-feedback: 30%
  - Manager + Client combined: 70%
  - Peer feedback: Not used in appraisals

### Quarterly & Yearly Analysis
- Above scoring methodology applies to each **quarter**
- **Yearly sheet data** will be used for generating **appraisal emails**
- An algorithm will be developed to calculate yearly performance metrics from quarterly data

### AI Chatbot Insights
Based on the feedback rating, the chatbot will:
- Identify **areas of improvement** for the employee
- Highlight **what the employee is already doing well**

### Discrepancy Alerts
- If there is a **rating difference > 1** between self-feedback and Manager/Client feedback, an **alert email** will be sent to the HR team

### Individual Employee Tracking
- Each employee will have an **individual sheet** tracking quarterly data
- The sheet will display both **positive and negative feedback summaries** for performance tracking
