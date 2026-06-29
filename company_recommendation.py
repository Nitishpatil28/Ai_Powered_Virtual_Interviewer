
import pandas as pd
import numpy as np
import pickle
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
import json
import os


class CompanyRecommendationEngine:
    def __init__(self):
        self.companies_data = self.load_companies_data()
        self.random_forest_model = None
        self.decision_tree_model = None
        self.scaler = None
        self.label_encoder = None
        self.feature_columns = [
            'skills_match',
            'experience_match',
            'education_match',
            'location_match',
            'industry_match']

        # Try to load existing models
        self.load_models()

    def load_companies_data(self):
        """Load company profiles from JSON file"""
        try:
            with open('company_profiles.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # If file doesn't exist, create a basic structure with 10 companies
            companies = {
                "companies": [
                    {"name": "Google", "industry": "Technology", "locations": ["Mountain View", "San Francisco", "New York"],
                     "skills_required": ["Python", "Java", "Machine Learning", "Cloud Computing"],
                     "education_levels": ["Bachelor", "Master", "PhD"], "experience_levels": ["Entry", "Mid", "Senior"]},
                    {"name": "Microsoft", "industry": "Technology", "locations": ["Redmond", "San Francisco", "New York"],
                     "skills_required": ["C#", ".NET", "Azure", "AI"],
                     "education_levels": ["Bachelor", "Master", "PhD"], "experience_levels": ["Entry", "Mid", "Senior"]},
                    {"name": "Amazon", "industry": "E-commerce/Technology", "locations": ["Seattle", "Austin", "New York"],
                     "skills_required": ["Java", "Python", "AWS", "Data Analysis"],
                     "education_levels": ["Bachelor", "Master", "PhD"], "experience_levels": ["Entry", "Mid", "Senior"]},
                    {"name": "Apple", "industry": "Technology", "locations": ["Cupertino", "Austin", "New York"],
                     "skills_required": ["Swift", "Objective-C", "iOS Development", "UI/UX"],
                     "education_levels": ["Bachelor", "Master", "PhD"], "experience_levels": ["Entry", "Mid", "Senior"]},
                    {"name": "Facebook", "industry": "Technology/Social Media", "locations": ["Menlo Park", "New York", "Seattle"],
                     "skills_required": ["React", "JavaScript", "PHP", "Data Science"],
                     "education_levels": ["Bachelor", "Master", "PhD"], "experience_levels": ["Entry", "Mid", "Senior"]},
                    {"name": "Netflix", "industry": "Entertainment/Technology", "locations": ["Los Gatos", "Los Angeles", "New York"],
                     "skills_required": ["Java", "Python", "Data Engineering", "Cloud Architecture"],
                     "education_levels": ["Bachelor", "Master", "PhD"], "experience_levels": ["Entry", "Mid", "Senior"]},
                    {"name": "Tesla", "industry": "Automotive/Technology", "locations": ["Palo Alto", "Austin", "New York"],
                     "skills_required": ["Python", "C++", "Embedded Systems", "AI"],
                     "education_levels": ["Bachelor", "Master", "PhD"], "experience_levels": ["Entry", "Mid", "Senior"]},
                    {"name": "IBM", "industry": "Technology/Consulting", "locations": ["Armonk", "Austin", "New York"],
                     "skills_required": ["Java", "Python", "Cloud", "AI/ML"],
                     "education_levels": ["Bachelor", "Master", "PhD"], "experience_levels": ["Entry", "Mid", "Senior"]},
                    {"name": "Oracle", "industry": "Technology/Database", "locations": ["Redwood City", "Austin", "New York"],
                     "skills_required": ["Java", "SQL", "Cloud Services", "Database Management"],
                     "education_levels": ["Bachelor", "Master", "PhD"], "experience_levels": ["Entry", "Mid", "Senior"]},
                    {"name": "Accenture", "industry": "Consulting/Technology", "locations": ["New York", "Chicago", "San Francisco"],
                     "skills_required": ["Java", "Python", "Cloud", "Consulting Skills"],
                     "education_levels": ["Bachelor", "Master", "PhD"], "experience_levels": ["Entry", "Mid", "Senior"]}
                ]
            }

            # Save the basic structure
            with open('company_profiles.json', 'w') as f:
                json.dump(companies, f, indent=4)

            return companies

    def load_models(self):
        """Load pre-trained models if they exist"""
        try:
            with open('models/random_forest_model.pkl', 'rb') as f:
                self.random_forest_model = pickle.load(f)
            with open('models/decision_tree_model.pkl', 'rb') as f:
                self.decision_tree_model = pickle.load(f)
            with open('models/scaler.pkl', 'rb') as f:
                self.scaler = pickle.load(f)
            with open('models/label_encoder.pkl', 'rb') as f:
                self.label_encoder = pickle.load(f)
        except (FileNotFoundError, pickle.UnpicklingError, ImportError, AttributeError) as e:
            print(f"Models could not be loaded ({type(e).__name__}: {e}). Will train new models.")
            # Reset models to None so they will be retrained
            self.random_forest_model = None
            self.decision_tree_model = None
            self.scaler = None
            self.label_encoder = None

    def save_models(self):
        """Save the trained models"""
        # Create models directory if it doesn't exist
        os.makedirs('models', exist_ok=True)

        with open('models/random_forest_model.pkl', 'wb') as f:
            pickle.dump(self.random_forest_model, f)
        with open('models/decision_tree_model.pkl', 'wb') as f:
            pickle.dump(self.decision_tree_model, f)
        with open('models/scaler.pkl', 'wb') as f:
            pickle.dump(self.scaler, f)
        with open('models/label_encoder.pkl', 'wb') as f:
            pickle.dump(self.label_encoder, f)

    def preprocess_candidate_data(self, candidate_profile):
        """Extract and preprocess candidate data for model input"""
        # Default values
        processed_data = {
            'skills_match': 0.5,  # Default to 50% match
            'experience_match': 0.5,
            'education_match': 0.5,
            'location_match': 0.5,
            'industry_match': 0.5
        }

        if not candidate_profile:
            return processed_data

        # Process skills match
        if 'skills' in candidate_profile and candidate_profile['skills']:
            # This would be more sophisticated in a real implementation
            # For now, we'll use a simple approach
            processed_data['skills_match'] = min(1.0, len(candidate_profile['skills']) / 5.0)

        # Process experience match
        if 'experience' in candidate_profile:
            # Convert years of experience to a match score (0-1)
            exp_years = candidate_profile['experience']
            if isinstance(exp_years, str):
                try:
                    exp_years = float(exp_years.split()[0])
                except BaseException:
                    exp_years = 0
            processed_data['experience_match'] = min(1.0, exp_years / 10.0)

        # Process education match
        if 'education' in candidate_profile:
            education = candidate_profile['education'].lower()
            if 'phd' in education or 'doctorate' in education:
                processed_data['education_match'] = 1.0
            elif 'master' in education:
                processed_data['education_match'] = 0.8
            elif 'bachelor' in education:
                processed_data['education_match'] = 0.6
            else:
                processed_data['education_match'] = 0.4

        # Process location match (simplified)
        if 'location' in candidate_profile:
            # In a real implementation, this would check against company locations
            processed_data['location_match'] = 0.7  # Default to 70% match

        # Process industry match (simplified)
        if 'industry' in candidate_profile:
            # In a real implementation, this would check against company industries
            processed_data['industry_match'] = 0.7  # Default to 70% match

        return processed_data

    def generate_training_data(self):
        """Generate synthetic training data for model training"""
        # In a real implementation, this would use actual historical data
        # For now, we'll generate synthetic data
        np.random.seed(42)
        n_samples = 1000

        # Generate random features
        X = np.random.rand(n_samples, len(self.feature_columns))

        # Generate random company labels
        company_names = [company['name'] for company in self.companies_data['companies']]
        y = np.random.choice(company_names, n_samples)

        # Create DataFrame
        df = pd.DataFrame(X, columns=self.feature_columns)
        df['company'] = y

        return df

    def train_models(self):
        """Train the recommendation models"""
        # Generate training data
        df = self.generate_training_data()

        # Prepare features and target
        X = df[self.feature_columns]
        y = df['company']

        # Encode target labels
        self.label_encoder = LabelEncoder()
        y_encoded = self.label_encoder.fit_transform(y)

        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y_encoded, test_size=0.2, random_state=42
        )

        # Train Random Forest model
        self.random_forest_model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.random_forest_model.fit(X_train, y_train)

        # Train Decision Tree model
        self.decision_tree_model = DecisionTreeClassifier(random_state=42)
        self.decision_tree_model.fit(X_train, y_train)

        # Save the models
        self.save_models()

        # Return model accuracy
        rf_accuracy = self.random_forest_model.score(X_test, y_test)
        dt_accuracy = self.decision_tree_model.score(X_test, y_test)

        return {
            'random_forest_accuracy': rf_accuracy,
            'decision_tree_accuracy': dt_accuracy
        }

    def recommend_companies(self, candidate_profile, algorithm='random_forest', top_n=5):
        """Recommend companies based on candidate profile"""
        if not self.random_forest_model or not self.decision_tree_model:
            # Train models if they don't exist
            self.train_models()

        # Preprocess candidate data
        candidate_data = self.preprocess_candidate_data(candidate_profile)
        X = pd.DataFrame([candidate_data])

        # Scale features
        X_scaled = self.scaler.transform(X)

        # Select model
        model = self.random_forest_model if algorithm == 'random_forest' else self.decision_tree_model

        # Get predictions and probabilities
        predictions_proba = model.predict_proba(X_scaled)[0]

        # Get all classes and their probabilities
        classes = model.classes_
        company_names = self.label_encoder.inverse_transform(classes)

        # Create a list of (company, probability) tuples
        company_probabilities = list(zip(company_names, predictions_proba))

        # Sort by probability (descending)
        company_probabilities.sort(key=lambda x: x[1], reverse=True)

        # Return top N recommendations as a list of dictionaries
        recommendations = []
        for company, probability in company_probabilities[:top_n]:
            # Get company details
            company_details = next(
                (c for c in self.companies_data['companies'] if c['name'] == company),
                None
            )

            if company_details:
                recommendations.append({
                    'name': company,
                    'match_percentage': round(probability * 100, 2),
                    'industry': company_details.get('industry', 'Unknown'),
                    'locations': company_details.get('locations', []),
                    'skills_required': company_details.get('skills_required', [])
                })

        return recommendations


# Create a singleton instance
company_recommender = CompanyRecommendationEngine()
