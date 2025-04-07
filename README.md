# ShiftWise: Revolutionizing Shift Management

<div align="center">
  <img src="./docs/images/logo.png" alt="ShiftWise Logo" width="220"/>
  <br>
  <a href="https://shiftwise-6b603db1db32.herokuapp.com/" target="_blank">
    <strong>Visit ShiftWise Live App »</strong>
  </a>
</div>

<br>

<div align="center">
  <img src="./docs/images/responsive-image-multiple-devices.png" alt="ShiftWise Responsive Design" width="100%"/>
  <p><em>ShiftWise - Optimized for all devices and screen sizes</em></p>
</div>

## Overview

ShiftWise is a comprehensive shift management platform designed for workforce scheduling and management in healthcare settings. Built with Django, it offers secure authentication with MFA, profile management, shift tracking, reporting dashboards, and subscription services powered by Stripe.

<div align="center">
  <table>
    <tr>
      <td align="center">
        <img src="./docs/images/mfa-enabled.png" alt="MFA Security" width="100%"/>
        <br><strong>Enhanced Security</strong>
      </td>
      <td align="center">
        <img src="./docs/images/shift-list-view.png" alt="Shift Management" width="100%"/>
        <br><strong>Intuitive Shift Management</strong>
      </td>
      <td align="center">
        <img src="./docs/images/price-cards-dark-mode.png" alt="Subscription Plans" width="100%"/>
        <br><strong>Flexible Subscription Plans</strong>
      </td>
    </tr>
  </table>
</div>

## ✨ Key Features

- **Multi-Factor Authentication (MFA)** for enhanced security
- **Role-based Access Control** for agencies, staff, and administrators
- **Comprehensive Shift Management** with digital completion signatures
- **Location Verification** for shift completion
- **Subscription Management** with Stripe integration
- **Advanced Reporting Dashboard** for performance analytics
- **Dark Mode Support** for reduced eye strain
- **Responsive Design** that works across all devices

<div align="center">
  <img src="./docs/images/hero-section.png" alt="ShiftWise Hero Section" width="90%"/>
</div>

---

## Table of Contents

1. [Introduction](#introduction)
2. [Strategy Plane](#strategy-plane)
3. [Scope Plane](#scope-plane)
4. [Structure Plane](#structure-plane)
5. [Skeleton Plane](#skeleton-plane)
6. [Surface Plane](#surface-plane)
7. [Features](#features)
8. [Technologies Used](#technologies-used)
9. [Setup and Deployment](#setup-and-deployment)
10. [Database Structure](#database-structure)
11. [Usage](#usage)
12. [Security Features](#security-features)
13. [API Integration](#api-integration)
14. [Testing](#testing)
15. [Credits and Acknowledgements](#credits-and-acknowledgements)
16. [Future Development](#future-development)

---

## Introduction

ShiftWise is a cutting-edge shift management platform designed to streamline scheduling for care home agencies and their employees. Leveraging the power of Django, ShiftWise offers a comprehensive array of features that facilitate efficient shift assignments, secure user authentication, profile management, email notifications, insightful reporting dashboards, and flexible subscription-based services.

<div align="center">
  <img src="./docs/images/homepage-image.png" alt="Homepage of ShiftWise" width="90%"/>
</div>

The platform aims to minimize administrative overhead, enhance communication, and provide actionable analytics to optimize workforce management.

This project represents the culmination of a series of milestones undertaken as part of the Code Institute Diploma in Web Application Development, showcasing expertise in full-stack development, security best practices, and responsive design.

---

## Strategy Plane

### Project Goals

ShiftWise was developed with the following objectives:

- **For Agencies:** Simplify the process of assigning, tracking, and managing employee shifts.
- **For Employees:** Provide a user-friendly interface to view, accept, and manage their shift schedules.
- **For Administrators:** Offer advanced tools for monitoring shift activities, generating reports, and managing subscriptions.

### Target Audience

- **Agencies:** Care home agencies requiring efficient shift scheduling and management for their workforce.
- **Employees (of Agencies):** Caregivers seeking clarity and control over their shift assignments.
- **Administrators (Agency Owners, Agency Managers, Superusers):** Personnel responsible for overseeing the operational aspects of shift management within the platform.

### User Stories

<div align="center">
  <img src="./docs/images/nav-bar.png" alt="Navigation Bar" width="90%"/>
</div>

#### Guest Users

- **Understand Purpose:** As a visitor, I want to understand the purpose of ShiftWise without needing to log in so that I can decide if it suits my needs.
- **Easy Navigation:** As a visitor, I want to easily navigate to the signup or login pages from the homepage.

#### Registered Users

- **Profile Management:** As a registered user, I want to create, view, edit, and delete my profile to maintain up-to-date personal information.
- **Shift Visibility:** As a registered user, I want to view my assigned shifts and receive notifications for upcoming shifts.
- **Subscription Management:** As a registered user, I want to manage my subscriptions to access premium features.

#### Agency Administrators

- **Efficient Shift Assignment:** As an agency administrator, I want to assign shifts to employees efficiently to ensure optimal workforce distribution.
- **Report Generation:** As an agency administrator, I want to see or generate reports on shift activities to analyze performance and attendance.
- **User Role Management:** As an agency administrator, I want to manage user roles and permissions to maintain platform security.

#### Superusers

- **Comprehensive Oversight:** As a superuser, I want to have full access to all aspects of the platform to manage agencies, users, shifts, and system settings.
- **Advanced Reporting:** As a superuser, I want to generate and view advanced reports to monitor overall platform performance and usage.
- **System Maintenance:** As a superuser, I want to perform system maintenance tasks, such as managing subscriptions, overseeing security settings, and handling escalated support issues.

---

## Scope Plane

### Functional Requirements

ShiftWise encompasses the following functionalities:

- **User Authentication:**
  - Secure registration, login, and logout processes with multi-factor authentication (MFA).
  - Password reset and recovery mechanisms.
- **Profile Management:**
  - Users can update their personal information and profile pictures.
  - Address management with autocomplete functionality using Google Places API.
- **Shift Management:**
  - Agencies can create, assign, and manage shifts for employees.
  - Employees can accept or decline shift assignments.
- **Notifications:**
  - Email notifications for shift assignments, updates, and reminders.
  - UI CRUD feedback messages to inform users about actions.
- **Reporting Dashboard:**
  - Visual analytics for shift activities, employee performance, and other key metrics.
- **Subscriptions:**
  - Tiered subscription plans offering varying levels of access and features.
  - Integration with Stripe for payment processing.
- **Admin Controls:**
  - Comprehensive tools for managing users, shifts, subscriptions, and platform settings.
- **Security:**
  - Role-based access control (RBAC).
  - Secure file uploads to AWS S3 using `django-storages`.
  - SSL/TLS encryption.

### Content Requirements

- **User Profiles:**
  - Detailed profiles including personal information, role designation, and shift history.
- **Shifts:**
  - Comprehensive details for each shift, including date, time, assigned employee, and status.
- **Notifications:**
  - Clear and concise messages informing users of important updates.
- **Reports:**
  - Visual and textual reports generated from shift and user data.
- **Subscription Plans:**
  - Descriptions of available subscription tiers and their respective benefits.

---

## Structure Plane

### Site Map

- **Home Page**
  - Overview of ShiftWise features.
  - Call-to-action for signup and login.
  - Testimonials and user feedback.
- **User Dashboard**
  - View assigned shifts.
  - Manage profile and settings.
  - Access notifications.
  - Subscription management.
- **Agency Dashboard**
  - Create and assign shifts.
  - View employee shift schedules.
  - Generate and view reports.
  - Manage subscriptions and user roles.
- **Superuser Dashboard**
  - Comprehensive oversight of all agencies and users.
  - Advanced reporting and analytics.
  - System settings and maintenance tools.
- **Reporting Dashboard**
  - Visual analytics on shift activities.
  - Performance metrics for employees.
- **Authentication Pages**
  - Signup, login, password reset, and MFA verification.
- **Admin Panel**
  - Manage users, shifts, subscriptions, and platform settings.

### Navigation Structure

- **Top Navigation Bar**

  The navigation bar adapts based on user role and authentication status, providing contextual access to relevant features.

  <div align="center">
    <img src="./docs/images/profile-and-logout-buttons.png" alt="Profile and Logout Navigation" width="90%"/>
  </div>

- **Footer**

  <div align="center">
    <img src="./docs/images/footer-image.png" alt="Footer Section" width="90%"/>
  </div>

---

## Skeleton Plane

The ShiftWise skeleton emphasizes user-friendly navigation and intuitive layouts. Key pages are organized to ensure that users can easily access and manage their shifts, profiles, and subscriptions.

### Wireframes

ShiftWise's design was meticulously planned using wireframes to map out the user journey and interface.

<div align="center">
  <table>
    <tr>
      <td>
        <strong>Home Page Wireframe</strong><br>
        <a href="./docs/wireframes/shiftwise-home-page-desktop-and-mobile.jpg" target="_blank">
          <img src="./docs/wireframes/shiftwise-home-page-desktop-and-mobile.jpg" alt="Home Page Wireframe" width="100%"/>
        </a>
      </td>
      <td>
        <strong>Dashboard Wireframe</strong><br>
        <a href="./docs/wireframes/shiftwise-dashboard-one.jpg" target="_blank">
          <img src="./docs/wireframes/shiftwise-dashboard-one.jpg" alt="Dashboard Wireframe" width="100%"/>
        </a>
      </td>
    </tr>
    <tr>
      <td>
        <strong>Manage Agencies Wireframe</strong><br>
        <a href="./docs/wireframes/shiftwise-manage-agencies.jpg" target="_blank">
          <img src="./docs/wireframes/shiftwise-manage-agencies.jpg" alt="Manage Agencies Wireframe" width="100%"/>
        </a>
      </td>
      <td>
        <strong>View Shifts Wireframe</strong><br>
        <a href="./docs/wireframes/shiftwise-view-shifts.jpg" target="_blank">
          <img src="./docs/wireframes/shiftwise-view-shifts.jpg" alt="View Shifts Wireframe" width="100%"/>
        </a>
      </td>
    </tr>
  </table>
</div>

---

## Surface Plane

The visual design of ShiftWise combines modern aesthetics with functionality, ensuring an engaging user experience.

### Visual Design

- **Hero Section:**

<div align="center">
  <img src="./docs/images/hero-section.png" alt="Hero Section" width="90%"/>
</div>

- **Features Section:**

<div align="center">
  <img src="./docs/images/features-buttons.png" alt="Features Section" width="90%"/>
</div>

- **Testimonials:**

<div align="center">
  <img src="./docs/images/testimonials.png" alt="Testimonials" width="90%"/>
</div>

- **Dark Mode:**

<div align="center">
  <table>
    <tr>
      <td>
        <img src="./docs/images/dark-mode-button.png" alt="Dark Mode Toggle" width="100%"/>
        <p align="center"><strong>Dark Mode Toggle</strong></p>
      </td>
      <td>
        <img src="./docs/images/dark-mode-responsive-view.png" alt="Dark Mode View" width="100%"/>
        <p align="center"><strong>Dark Mode Interface</strong></p>
      </td>
    </tr>
  </table>
</div>

- **Color Scheme:**

  - **Primary Color (#0056b3):** Utilized for headers, buttons, and active elements to establish brand identity.
  - **Secondary Color (#ffffff):** Used for backgrounds and text to ensure readability.
  - **Accent Color (#ffc107):** Highlights important features and calls-to-action.
  - **Dark Mode (#121212):** Provides a sleek, modern look for users preferring dark themes.

- **Typography:**

  - **Roboto:** Chosen for its clarity and modern feel, enhancing readability across devices.

- **Responsive Design:**

<div align="center">
  <img src="./docs/images/responsive-navbar.png" alt="Responsive Navbar" width="90%"/>
  <p><em>The navigation adapts seamlessly to different screen sizes</em></p>
</div>

---

## Features

ShiftWise offers a comprehensive suite of features tailored to the needs of care home agencies and their employees.

### User Authentication and Profile Management

<div align="center">
  <table>
    <tr>
      <td>
        <img src="./docs/images/mfa-login-verification-page.png" alt="MFA Login Verification" width="100%"/>
        <p align="center"><strong>Multi-Factor Authentication</strong></p>
      </td>
      <td>
        <img src="./docs/images/profile.png" alt="User Profile" width="100%"/>
        <p align="center"><strong>User Profile Management</strong></p>
      </td>
    </tr>
  </table>
</div>

- **Secure Registration and Login:**
  - Implements Django Allauth for robust user authentication.
  - Multi-Factor Authentication (MFA) enhances account security.

- **Profile Customization:**
  - Users can update personal information, including profile pictures.
  - Address fields with autocomplete using Google Places API.

- **Role Designation:**
  - Role designation (Agency Owner, Agency Manager, Agency Staff, Superuser) determines access levels.

### Shift Management

<div align="center">
  <table>
    <tr>
      <td>
        <img src="./docs/images/shift-list-view.png" alt="Shift List View" width="100%"/>
        <p align="center"><strong>Shift List View</strong></p>
      </td>
      <td>
        <img src="./docs/images/shift-detail-view.png" alt="Shift Detail View" width="100%"/>
        <p align="center"><strong>Shift Detail View</strong></p>
      </td>
    </tr>
    <tr>
      <td>
        <img src="./docs/images/create-shift-button.png" alt="Create Shift Button" width="100%"/>
        <p align="center"><strong>Create Shift Button</strong></p>
      </td>
      <td>
        <img src="./docs/images/shift-completion-modal.png" alt="Shift Completion Modal" width="100%"/>
        <p align="center"><strong>Shift Completion with Signature</strong></p>
      </td>
    </tr>
  </table>
</div>

- **Creating Shifts:**
  - Agency admins can create new shifts specifying details like name, date, time, and role.

- **Shift List and Detail Views:**
  - Users can view a list of available shifts and detailed information about each shift.

- **Shift Completion:**
  - Employees can complete shifts by capturing their location and providing a digital signature.

- **CRUD Operations:**
  - Create, read, update, and delete shifts with detailed information including timing, capacity, and financials.

### Notifications

<div align="center">
  <img src="./docs/images/successful-subscription-notification.png" alt="Notification Example" width="90%"/>
  <p><em>Successful subscription notification example</em></p>
</div>

- **Email Notifications:**
  - Users receive email notifications for shift assignments and updates for general activities like staff invites to the platform.

- **UI Feedback Messages:**
  - Real-time UI feedback messages with consistent styling inform users about actions such as creating, updating, or deleting shifts.

### Reporting Dashboard

<div align="center">
  <img src="./docs/images/agency-owner-and-manager-dashboard.png" alt="Agency Dashboard" width="90%"/>
  <p><em>Agency Owner Dashboard with reporting capabilities</em></p>
</div>

- **Analytics:**
  - Visual representations of shift activities, attendance rates, and employee performance metrics I designed to provide actionable insights.

- **Export Options:**
  - Custom-built functionality to generate reports in CSV for offline analysis and record-keeping.

### Subscriptions

<div align="center">
  <table>
    <tr>
      <td>
        <img src="./docs/images/price-cards-dark-mode.png" alt="Subscription Plans" width="100%"/>
        <p align="center"><strong>Subscription Plans</strong></p>
      </td>
      <td>
        <img src="./docs/images/payment-stripe.png" alt="Stripe Payment" width="100%"/>
        <p align="center"><strong>Stripe Payment Integration</strong></p>
      </td>
    </tr>
    <tr>
      <td>
        <img src="./docs/images/payment-stripe-test-success.png" alt="Payment Success" width="100%"/>
        <p align="center"><strong>Payment Success</strong></p>
      </td>
      <td>
        <img src="./docs/images/manage-subscription-view.png" alt="Manage Subscription" width="100%"/>
        <p align="center"><strong>Subscription Management</strong></p>
      </td>
    </tr>
  </table>
</div>

- **Tiered Subscription Plans:**
  - **Basic:** Limited number of shifts and features.
  - **Pro:** Additional analytics and reporting features.
  - **Enterprise:** Unlimited staff, shifts, and advanced capabilities.

- **Payment Integration:**
  - Seamless subscription management with Stripe for secure billing and payment processing.

### Admin Controls

<div align="center">
  <table>
    <tr>
      <td>
        <img src="./docs/images/django-admin-panel.png" alt="Django Admin Panel" width="100%"/>
        <p align="center"><strong>Django Admin Panel</strong></p>
      </td>
      <td>
        <img src="./docs/images/superuser-dashboard.png" alt="Superuser Dashboard" width="100%"/>
        <p align="center"><strong>Superuser Dashboard</strong></p>
      </td>
    </tr>
  </table>
</div>

- **Comprehensive Management Tools:**
  - Manage users, shifts, subscriptions, and platform settings through the Django admin interface.

- **Content Moderation:**
  - Maintain platform integrity and security by overseeing user-generated content and activities.

### Responsive Design

<div align="center">
  <img src="./docs/images/responsive-image-multiple-devices.png" alt="Responsive Design" width="90%"/>
  <p><em>ShiftWise adapts to all device sizes</em></p>
</div>

- **Cross-Device Compatibility:**
  - Ensures optimal user experience across desktops, tablets, and mobile devices with a mobile-first approach.

- **Dynamic Components:**
  - Enhanced user interactions through JavaScript-powered elements like modals and autocomplete fields.

### Features Testing

ShiftWise has undergone extensive testing to ensure reliability across all features. For a comprehensive breakdown of testing methodologies, tools, results, issue resolutions, and visual validation evidence, please refer to the detailed [TESTING.md](./TESTING.md) document.

---

## Technologies Used

ShiftWise leverages a combination of modern technologies to deliver a robust and scalable platform.

### Backend

- **Framework:** Django version 5.1.2
- **Database:** PostgreSQL (deployed with SSL for enhanced security)
- **Storage:** AWS S3 for media and static files using `django-storages`

### Frontend

- **HTML5 & CSS3:** Structuring and styling the web pages.
- **Bootstrap 4:** For responsive design and pre-built UI components.
- **JavaScript:** Enhancing interactivity and dynamic content updates.
- **jQuery:** Simplifying DOM manipulation and event handling.
- **Font Awesome:** Providing scalable vector icons.

### Third-Party Integrations

- **Stripe:** Manages subscription-based billing and payment processing.
- **Google Places API:** Provides address autocomplete and suggestions for enhanced user experience.
- **OpenStreetMap:** Used for capturing geo location data when completing shifts.
- **Signature Pad (JavaScript):** Enables digital signature capture for shift completion.
- **SendGrid API:** Powers all transactional emails including notifications for shift assignments and updates.

### DevOps

- **Heroku:** For deploying and hosting the application.
- **Git & GitHub:** Version control and repository management.

### Security

- **Django's Built-in Security Features:** Including CSRF protection, XSS protection, and secure password storage.
- **SSL/TLS:** Ensures secure data transmission.
- **MFA Implementation:** Using TOTP for multi-factor authentication.

---

## Setup and Deployment

Deploying ShiftWise ensures that care home agencies can access the platform reliably and securely. Follow the steps below to set up and deploy ShiftWise both locally and to Heroku.

### Prerequisites

Before setting up ShiftWise, ensure you have the following installed:

- **Python 3.9+**
- **Git:** Version control and cloning the repository.
- **Virtual Environment:** Recommended for managing project dependencies.
- **PostgreSQL 14+:** Database management system.
- **Heroku CLI:** For deploying the application to Heroku.
- **AWS Account:** For S3 storage of media and static files.
- **Google Cloud:** For setting up Google Places API for address autocomplete services.

### Installation Steps

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/shiftwise.git
   cd shiftwise
   ```

2. **Create a Virtual Environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**

   Create a `.env` file in the root directory and add necessary configurations:
   
   ```
   # Email Configuration (SendGrid)
   EMAIL_HOST=smtp.sendgrid.net
   EMAIL_PORT=587
   EMAIL_USE_TLS=True
   EMAIL_HOST_USER=apikey
   EMAIL_HOST_PASSWORD=your_sendgrid_api_key
   DEFAULT_FROM_EMAIL=your_verified_sender@example.com
   ```
   
   Additional environment variables are required for other services.

5. **Apply Migrations**

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Create a Superuser**

   ```bash
   python manage.py createsuperuser
   ```

7. **Run the Development Server**

   ```bash
   python manage.py runserver
   ```

### Deploying to Heroku

1. **Log in to Heroku**

   ```bash
   heroku login
   ```

2. **Create a Heroku App**

   ```bash
   heroku create shiftwise-app
   ```

3. **Set Environment Variables on Heroku**

   Configure all required environment variables in the Heroku dashboard or using the CLI.

4. **Deploy the Application**

   ```bash
   git push heroku main
   ```

5. **Apply Migrations on Heroku**

   ```bash
   heroku run python manage.py migrate
   ```

---

## Database Structure

<div align="center">
  <img src="./docs/images/erd.png" alt="Entity Relationship Diagram" width="90%"/>
  <p><em>ShiftWise Database Entity Relationship Diagram</em></p>
</div>

ShiftWise utilizes a relational database (PostgreSQL) to manage and store data efficiently. The key models include User, Agency, Shift, ShiftAssignment, Subscription, Plan, and Notification, with appropriate relationships between them to ensure data integrity and efficient querying.

---

## Usage

ShiftWise leverages Django's powerful admin interface for managing shifts, assignments, and staff performance. Below is a guide to navigating and utilizing the features effectively.

### User Registration and Authentication

- **Registration**: Users can sign up by providing their email and password.
- **Login**: Secure login with options for MFA adds an extra layer of security.

### Profile Management

- **Updating Information**: Users can update their profile details, including changing their email and uploading a new profile picture.
- **Multi-Factor Authentication (MFA)**: Users can enable MFA for enhanced security during login.

### Shift Management Operations

<div align="center">
  <table>
    <tr>
      <td>
        <img src="./docs/images/available-workers-view.png" alt="Available Workers" width="100%"/>
        <p align="center"><strong>Available Workers View</strong></p>
      </td>
      <td>
        <img src="./docs/images/shift-book-and-detail-view-buttons.png" alt="Shift Booking" width="100%"/>
        <p align="center"><strong>Shift Booking Options</strong></p>
      </td>
    </tr>
  </table>
</div>

- **Creating Shifts**: Agency admins can create new shifts specifying details like name, date, time, and role.
- **Assigning Shifts**: Admins can assign shifts to employees based on availability and role requirements.
- **Managing Shifts**: Shifts can be edited or deleted as needed.

---

## Security Features

ShiftWise prioritizes security to protect user data and ensure platform integrity. Below are key security measures implemented:

### User Authentication and Authorization

- **Password Hashing**: Utilizes Django's built-in password hashing mechanisms.
- **Role-Based Access Control (RBAC)**: Differentiates access levels between user roles.
- **Multi-Factor Authentication (MFA)**: Adds an additional security layer during user login.

### Data Validation and Sanitization

- **Form Validation**: All user inputs are validated on both client and server sides.
- **Sanitization**: Inputs are sanitized to guard against SQL injection, XSS, and other vulnerabilities.

### HTTPS and SSL

- **Secure Communication**: The platform enforces HTTPS to ensure data transmitted between the server and clients is encrypted.

---

## API Integration

ShiftWise integrates with several external APIs to enhance functionality and user experience.

- **Google Places API**
  - Enables address autocomplete and geocoding for accurate shift location mapping.

- **Stripe API**
  - Handles subscription payments securely, managing billing cycles and transaction records.

- **Signature Pad**
  - Captures employee signatures during shift completions, storing them securely for verification purposes.

---

## Testing

ShiftWise has undergone extensive testing to ensure reliability across all features. For a comprehensive breakdown of testing methodologies, tools, results, and issue resolutions, please refer to the detailed [TESTING.md](./TESTING.md) document.

### Testing Overview

| Test Category | Tests Performed | Pass Rate |
|---------------|----------------|-----------|
| Manual Feature Testing | 57 | 100% |
| Responsive Design | 13 | 100% |
| Code Validation | 28 | 100% |
| User Story Verification | 15 | 100% |
| Browser Compatibility | 5 | 100% |

---

## Credits and Acknowledgements

- **Contributors**
  - [Temitope Akingbala](https://github.com/topesoul) - Developer

- **References**
  - **Django Documentation**: For comprehensive guidance on Django functionalities.
  - **Bootstrap Documentation**: Assisted in implementing responsive design elements.
  - **Font Awesome**: Supplied scalable icons enhancing the UI.
  - **Stack Overflow**: Offered solutions to various development challenges.
  - **Heroku**: Facilitated seamless deployment and hosting of the application.

- **Code Resources**
  - **Code Institute's Learning Management Resources**: For overall project development tutorials, key source code and setup instructions e.g., AWS S3, Heroku
  - **Django**: The primary framework used for backend development.
  - **Django all-auth Documentation**: For implementation of user sessions mgt and MFA

- **Acknowledgements**
  - **Code Institute**: For the structured curriculum and invaluable support throughout the project.
  - **My Mentor, Student Care Staff and Peers**: For their feedback, support and encouragement.

---

## Future Development

While ShiftWise is feature-complete, the following enhancements are planned for future iterations:

- **Mobile Application**: Develop native mobile apps for iOS and Android.
- **Advanced Reporting**: Introduce more in-depth analytics and customizable reports.
- **Staff Wellbeing Platform**: Implement wellbeing check-ins and burnout prevention tools.
- **AI-Powered Scheduling**: Utilize machine learning to optimize shift assignments.
- **Integration with Calendar Apps**: Allow users to sync shifts with Google Calendar, Outlook, etc.
- **Enhanced Security Features**: Implement biometric authentication and advanced encryption methods.
- **Enhanced API for Third-Party Integrations**: Expand the current basic API implementation.
- **Multi-Language Support**: Expand the platform's accessibility by supporting multiple languages.

---

<div align="center">
  <p>ShiftWise - Transforming Healthcare Shift Management</p>
  <img src="./docs/images/social-section.png" alt="Social Media Section" width="50%"/>
</div>