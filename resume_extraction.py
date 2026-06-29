
import os
import re
import PyPDF2
import docx
import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import pickle


class ResumeExtractor:
    def __init__(self):
        # Download NLTK data if not already present
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')

        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords')

        try:
            nltk.data.find('corpora/wordnet')
        except LookupError:
            nltk.download('wordnet')

        # Initialize lemmatizer and stopwords
        self.lemmatizer = WordNetLemmatizer()
        self.stop_words = set(stopwords.words('english'))

        # Define patterns for extracting information
        self.email_pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}'
        self.phone_pattern = r'(\+\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}'
        self.education_keywords = [
            'bachelor',
            'master',
            'phd',
            'doctorate',
            'diploma',
            'degree',
            'university',
            'college']
        self.experience_keywords = ['experience', 'work', 'job', 'employment', 'career', 'professional']
        self.skill_keywords = ['skills', 'technologies', 'programming', 'languages', 'tools', 'frameworks', 'software']

        # Load pre-trained models if they exist
        self.skill_classifier = None
        self.load_models()

    def load_models(self):
        """Load pre-trained models if they exist"""
        try:
            with open('models/skill_classifier.pkl', 'rb') as f:
                self.skill_classifier = pickle.load(f)
        except FileNotFoundError:
            print("Skill classifier model not found. Will use rule-based extraction.")

    def extract_text_from_pdf(self, pdf_file):
        """Extract text from PDF file"""
        text = ""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            for page in pdf_reader.pages:
                text += page.extract_text()
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
        return text

    def extract_text_from_docx(self, docx_file):
        """Extract text from DOCX file"""
        text = ""
        try:
            doc = docx.Document(docx_file)
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
        except Exception as e:
            print(f"Error extracting text from DOCX: {e}")
        return text

    def extract_text(self, file_path):
        """Extract text from file based on its extension"""
        _, ext = os.path.splitext(file_path)

        if ext.lower() == '.pdf':
            return self.extract_text_from_pdf(file_path)
        elif ext.lower() == '.docx':
            return self.extract_text_from_docx(file_path)
        else:
            # Assume it's a text file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                print(f"Error extracting text from file: {e}")
                return ""

    def extract_contact_info(self, text):
        """Extract contact information from resume text"""
        contact_info = {}

        # Extract email
        emails = re.findall(self.email_pattern, text)
        if emails:
            contact_info['email'] = emails[0]

        # Extract phone number
        phones = re.findall(self.phone_pattern, text)
        if phones:
            contact_info['phone'] = phones[0]

        # Extract name (simplified - in a real implementation, this would be more sophisticated)
        lines = text.split('\n')
        if lines:
            # Assume the first line is the name
            contact_info['name'] = lines[0].strip()

        return contact_info

    def extract_education(self, text):
        """Extract education information from resume text"""
        education = []

        # Split text into sentences
        sentences = sent_tokenize(text)

        # Find sentences containing education keywords
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(keyword in sentence_lower for keyword in self.education_keywords):
                education.append(sentence.strip())

        return education

    def extract_experience(self, text):
        """Extract work experience from resume text"""
        experience = []

        # Split text into sentences
        sentences = sent_tokenize(text)

        # Find sentences containing experience keywords
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(keyword in sentence_lower for keyword in self.experience_keywords):
                experience.append(sentence.strip())

        # Try to extract years of experience
        years_pattern = r'(\d+)\s*(?:years?|yrs?)'
        years_matches = re.findall(years_pattern, text.lower())

        total_years = 0
        if years_matches:
            try:
                total_years = sum(int(years) for years in years_matches)
            except ValueError:
                pass

        return {
            'details': experience,
            'years': total_years
        }

    def extract_skills(self, text):
        """Extract skills from resume text"""
        # Common tech skills (in a real implementation, this would be more comprehensive)
        tech_skills = [
            'python', 'java', 'javascript', 'c++', 'c#', 'php', 'ruby', 'swift', 'kotlin',
            'html', 'css', 'react', 'angular', 'vue', 'node.js', 'django', 'flask', 'spring',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'git', 'sql', 'nosql',
            'mongodb', 'mysql', 'postgresql', 'oracle', 'tensorflow', 'pytorch', 'keras',
            'machine learning', 'deep learning', 'data science', 'ai', 'nlp', 'computer vision'
        ]

        # Tokenize text and normalize
        tokens = word_tokenize(text.lower())
        tokens = [self.lemmatizer.lemmatize(token)
                  for token in tokens if token.isalpha() and token not in self.stop_words]

        # Find skills
        found_skills = []
        for skill in tech_skills:
            if skill.lower() in tokens:
                found_skills.append(skill)

        return found_skills

    def process_resume(self, file_path):
        """Process a resume file and extract relevant information"""
        # Extract text from file
        text = self.extract_text(file_path)

        if not text:
            return {"error": "Could not extract text from the resume file."}

        # Extract different sections
        contact_info = self.extract_contact_info(text)
        education = self.extract_education(text)
        experience = self.extract_experience(text)
        skills = self.extract_skills(text)

        # Return structured data
        return {
            "contact_info": contact_info,
            "education": education,
            "experience": experience,
            "skills": skills,
            "raw_text": text
        }

    def match_candidate_to_company(self, candidate_data, company_profile):
        """Calculate how well a candidate matches a company profile"""
        # Initialize match scores
        skills_match = 0
        experience_match = 0
        education_match = 0

        # Calculate skills match
        if 'skills' in candidate_data and 'skills_required' in company_profile:
            candidate_skills = [skill.lower() for skill in candidate_data['skills']]
            required_skills = [skill.lower() for skill in company_profile['skills_required']]

            if required_skills:
                matched_skills = sum(
                    1 for skill in required_skills if any(
                        req_skill in skill for req_skill in required_skills))
                skills_match = matched_skills / len(required_skills)

        # Calculate experience match
        if 'experience' in candidate_data and 'experience_levels' in company_profile:
            candidate_years = candidate_data['experience'].get('years', 0)

            # Map experience levels to years
            exp_level_to_years = {
                'Entry': '0-2',
                'Mid': '2-5',
                'Senior': '5+'
            }

            # Simple logic: if candidate has any experience, they match
            experience_match = min(1.0, candidate_years / 5.0)  # Normalize to 0-1

        # Calculate education match
        if 'education' in candidate_data and 'education_levels' in company_profile:
            # Extract education level from education details
            education_text = ' '.join(candidate_data['education']).lower()

            # Check for highest education level
            if 'phd' in education_text or 'doctorate' in education_text:
                candidate_education = 'PhD'
            elif 'master' in education_text:
                candidate_education = 'Master'
            elif 'bachelor' in education_text:
                candidate_education = 'Bachelor'
            else:
                candidate_education = 'Other'

            # Check if candidate's education matches company requirements
            if candidate_education in company_profile['education_levels']:
                education_match = 1.0
            else:
                # Partial match based on education hierarchy
                education_hierarchy = ['Other', 'Bachelor', 'Master', 'PhD']
                candidate_idx = education_hierarchy.index(candidate_education)

                # Find the highest required education level
                highest_required_idx = 0
                for level in company_profile['education_levels']:
                    if level in education_hierarchy:
                        highest_required_idx = max(highest_required_idx, education_hierarchy.index(level))

                # Calculate match based on hierarchy
                education_match = candidate_idx / highest_required_idx if highest_required_idx > 0 else 0.5

        # Calculate overall match score
        overall_match = (skills_match + experience_match + education_match) / 3

        return {
            'skills_match': skills_match,
            'experience_match': experience_match,
            'education_match': education_match,
            'overall_match': overall_match
        }
