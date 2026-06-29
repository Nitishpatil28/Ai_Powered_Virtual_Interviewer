"""
Refactored ml_company_matcher.py
- Lightweight, modular matcher for company recommendations
- Uses SentenceTransformers embeddings when available, falls back to TF-IDF
- Provides resume parsing helpers (pdf/docx/text) and robust matching
- Stores/uses cached company embeddings in the `companies` table (embedding_json)

Tables expected (SQLite):
- companies(id INTEGER PRIMARY KEY, name TEXT, required_skills TEXT, role TEXT, embedding_json TEXT)
- students(email TEXT PRIMARY KEY, name TEXT, skills TEXT, resume_path TEXT, cgpa REAL, graduation_year INTEGER)

Functions exported:
- parse_resume(file_path) -> dict
- CompanyMatcher.precompute_company_embeddings(force=False)
- CompanyMatcher.match_parsed_resume(parsed_resume, top_k=10)
- get_company_recommendations_for_student(email, top_k=10)

NOTE: This module tries to be dependency-friendly. If `sentence_transformers` is installed,
it will use a compact model for better semantic matches. Otherwise it uses TF-IDF on company
skill text which still gives reasonable results.

Be careful to `pip install sentence-transformers` only if you have the bandwidth/CPU.
"""

import os
import re
import json
import sqlite3
from typing import List, Dict

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Optional heavy dependency
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
except Exception:
    SENTENCE_MODEL = None

# Load ML models for better scoring
# Temporarily disabled due to feature mismatch
RF_MODEL = None
SCALER = None

# try:
#     import joblib
#     RF_MODEL = joblib.load('models/random_forest_model.pkl')
#     SCALER = joblib.load('models/scaler.pkl')
# except Exception:
#     RF_MODEL = None
#     SCALER = None

# For PDF and DOCX parsing
try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    import docx2txt
except Exception:
    docx2txt = None

DB_PATH = os.environ.get('MATCHER_DB_PATH', 'users.db')

# ------------------------- Resume parsing utilities -------------------------


def _read_file_text(path: str) -> str:
    """Read text from pdf/docx/txt files with graceful fallbacks."""
    path = os.path.abspath(path)
    ext = os.path.splitext(path)[1].lower()
    text = ""

    if ext == '.pdf' and pdfplumber:
        try:
            with pdfplumber.open(path) as pdf:
                pages = [p.extract_text() or '' for p in pdf.pages]
            text = '\n'.join(pages)
        except Exception:
            text = ''

    if not text and ext in ('.doc', '.docx') and docx2txt:
        try:
            text = docx2txt.process(path) or ''
        except Exception:
            text = ''

    if not text and ext == '.txt':
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        except Exception:
            text = ''

    return text


def simple_keyword_extract(text: str, top_n: int = 60) -> List[str]:
    """Extract technical skills from resume text using predefined skill list."""
    # Comprehensive list of technical skills
    technical_skills = {
        # Programming Languages
        'python', 'java', 'javascript', 'c++', 'c#', 'c', 'php', 'ruby', 'swift', 'kotlin',
        'go', 'rust', 'scala', 'perl', 'r', 'matlab', 'typescript', 'dart', 'lua',

        # Web Technologies
        'html', 'css', 'react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask',
        'spring', 'laravel', 'asp.net', 'jquery', 'bootstrap', 'sass', 'less',

        # Databases
        'sql', 'mysql', 'postgresql', 'mongodb', 'oracle', 'sqlite', 'redis', 'cassandra',
        'elasticsearch', 'dynamodb', 'firebase',

        # Cloud & DevOps
        'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'gitlab', 'github',
        'terraform', 'ansible', 'puppet', 'chef', 'nginx', 'apache',

        # Data Science & ML
        'machine learning', 'deep learning', 'tensorflow', 'pytorch', 'keras', 'scikit-learn',
        'pandas', 'numpy', 'matplotlib', 'seaborn', 'jupyter', 'spark', 'hadoop',
        'data science', 'ai', 'nlp', 'computer vision', 'opencv',

        # Mobile Development
        'android', 'ios', 'react native', 'flutter', 'xamarin', 'cordova',

        # Tools & Frameworks
        'git', 'linux', 'ubuntu', 'windows', 'macos', 'bash', 'powershell', 'vim', 'vscode',
        'intellij', 'eclipse', 'pycharm', 'visual studio',

        # Other Technical Skills
        'api', 'rest', 'graphql', 'microservices', 'agile', 'scrum', 'kanban', 'oop',
        'design patterns', 'algorithms', 'data structures', 'testing', 'unit testing',
        'integration testing', 'selenium', 'postman', 'swagger'
    }

    # Clean and tokenize text
    text = re.sub(r'[^A-Za-z0-9\+\#\. ]', ' ', (text or '').lower())
    tokens = set(re.split(r'\s+', text))  # Use set to avoid duplicates

    # Find matching technical skills
    found_skills = []
    for skill in technical_skills:
        # Check for exact match
        if skill in tokens:
            found_skills.append(skill)
        # Check for multi-word skills (split and check if all parts are present)
        elif ' ' in skill:
            skill_parts = skill.split()
            if all(part in tokens for part in skill_parts):
                found_skills.append(skill)

    # Remove duplicates and limit to top_n
    found_skills = list(set(found_skills))[:top_n]
    return found_skills


def parse_resume(file_path: str) -> Dict:
    """Parse resume file and return a small structured dict.

    Output example:
    {
      'name': None,
      'skills': ['python','sql','opencv'],
      'cgpa': None,
      'graduation_year': None,
      'raw_text': '...'
    }
    """
    text = _read_file_text(file_path)
    skills = simple_keyword_extract(text, top_n=30)

    # try to get cgpa - handle both 4.0 and 10.0 scales
    cgpa = None
    cgpa_patterns = [
        r'(\d\.\d{1,2})\s*(?:cgpa|gpa|grade\s+point)',
        r'(?:cgpa|gpa|grade\s+point).*?(\d\.\d{1,2})',
        r'(\d{1,2}\.\d{1,2})\s*(?:cgpa|gpa)',
        r'(?:cgpa|gpa).*?(\d{1,2}\.\d{1,2})'
    ]

    for pattern in cgpa_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            try:
                cgpa_val = float(match.group(1))
                # If CGPA is between 0-4.0, assume it's out of 4.0 scale, convert to 10.0
                if 0 < cgpa_val <= 4.0:
                    cgpa = (cgpa_val / 4.0) * 10.0
                # If CGPA is between 4.1-10.0, assume it's already on 10.0 scale
                elif 4.1 <= cgpa_val <= 10.0:
                    cgpa = cgpa_val
                # If CGPA is unreasonably high (>10), ignore it
                elif cgpa_val > 10.0:
                    continue
                else:
                    cgpa = cgpa_val
                break
            except Exception:
                continue

    # graduation year - look for more specific patterns
    grad = None
    # Look for graduation-related patterns with years
    grad_patterns = [
        r'(?:graduation|graduated|passing|completion)\s*(?:year|in)?\s*(20\d{2})',
        r'(20\d{2})\s*(?:graduation|graduated|passing|completion)',
        r'class\s+of\s+(20\d{2})',
        r'(20\d{2})\s*(?:batch|passed|completed)'
    ]

    for pattern in grad_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            y = int(match.group(1))
            if 2000 < y < 2050:
                grad = y
                break

    # Fallback: if no specific graduation pattern found, look for recent years in education context
    if not grad:
        education_section = re.search(
            r'(?:education|academic|qualification).*?(?=experience|skills|projects|$)',
            text,
            re.I | re.DOTALL)
        if education_section:
            year_match = re.search(r'(20\d{2})', education_section.group(0))
            if year_match:
                y = int(year_match.group(1))
                if 2015 <= y <= 2030:  # More reasonable range for current students
                    grad = y

    return {
        'name': None,
        'skills': skills,
        'cgpa': cgpa,
        'graduation_year': grad,
        'raw_text': text
    }


# ------------------------- Company matcher -------------------------

class CompanyMatcher:
    """Encapsulates company loading, embedding and matching logic."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._companies = None  # cached list of company dicts
        self._tfidf_vec = None
        self._tfidf_matrix = None

    # ---------- Database helpers ----------
    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _load_companies(self) -> List[Dict]:
        """Load companies from the DB. Expected columns: id,name,required_skills,role,embedding_json(optional)"""
        if self._companies is not None:
            return self._companies

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, required_skills, role, embedding_json
            FROM companies
        """)
        rows = cur.fetchall()
        conn.close()

        companies = []
        for r in rows:
            cid, name, skills, role, emb_json = r
            companies.append({
                'id': cid,
                'name': name,
                'required_skills': skills or '',
                'role': role or '',
                'embedding': json.loads(emb_json) if emb_json else None
            })
        self._companies = companies
        return companies

    # ---------- Embedding & precompute ----------
    def precompute_company_embeddings(self, force: bool = False):
        """Ensure each company has an embedding stored in DB. Use SBERT if available, else TF-IDF.

        This function will update the companies table's embedding_json column.
        """
        companies = self._load_companies()
        if not companies:
            return 0

        texts = [f"{c['name']} {c['role']} {c['required_skills']}" for c in companies]

        if SENTENCE_MODEL and not force:
            try:
                embs = SENTENCE_MODEL.encode(texts, show_progress_bar=False)
                use_sentence = True
            except Exception:
                embs = None
                use_sentence = False
        else:
            use_sentence = False
            embs = None

        if not use_sentence:
            # TF-IDF fallback: compute TF-IDF matrix and store dense vectors (small)
            self._tfidf_vec = TfidfVectorizer(ngram_range=(1, 2), max_features=1000)
            self._tfidf_matrix = self._tfidf_vec.fit_transform(texts)
            # convert sparse rows to dense lists for storing (OK for small company lists)
            embs = [row.toarray().ravel().tolist() for row in self._tfidf_matrix]

        # persist embeddings to DB
        conn = self._connect()
        cur = conn.cursor()
        for c, emb in zip(companies, embs):
            emb_json = json.dumps(np.array(emb).tolist())
            cur.execute("UPDATE companies SET embedding_json = ? WHERE id = ?", (emb_json, c['id']))
        conn.commit()
        conn.close()

        # clear cached companies so next load picks up embeddings
        self._companies = None
        return len(embs)

    # ---------- Matching ----------
    def _ensure_embeddings_loaded(self):
        companies = self._load_companies()
        any_missing = any(c.get('embedding') is None for c in companies)

        # Also check if embeddings have inconsistent dimensions
        dimensions = [len(c.get('embedding', [])) for c in companies if c.get('embedding')]
        inconsistent_dims = len(set(dimensions)) > 1

        if any_missing or inconsistent_dims:
            # Force re-embedding all companies to ensure consistency
            self.precompute_company_embeddings(force=True)
            companies = self._load_companies()
        return companies

    def _embed_resume(self, parsed_resume: Dict):
        text = ' '.join((parsed_resume.get('skills') or [])[:60])

        # Check what embedding method companies are using by looking at the first company
        companies = self._load_companies()
        use_sbert = False
        if companies and companies[0].get('embedding'):
            # If company embeddings exist, check their dimension
            comp_emb_dim = len(companies[0]['embedding'])
            # SBERT typically has 384 dimensions, TF-IDF has variable (usually 1000 in our case)
            use_sbert = comp_emb_dim == 384  # Assume SBERT if 384 dimensions

        # Use the same method as companies
        if use_sbert and SENTENCE_MODEL:
            try:
                emb = SENTENCE_MODEL.encode([text], show_progress_bar=False)[0]
                return np.array(emb)
            except Exception:
                # If SBERT fails, fall back to TF-IDF
                pass

        # TF-IDF method
        if self._tfidf_vec is None:
            # build vectorizer from company texts
            texts = [f"{c['name']} {c['role']} {c['required_skills']}" for c in companies]
            self._tfidf_vec = TfidfVectorizer(ngram_range=(1, 2), max_features=1000)
            self._tfidf_matrix = self._tfidf_vec.fit_transform(texts)

        res_vec = self._tfidf_vec.transform([text])
        return res_vec.toarray().ravel()

    def match_parsed_resume(self, parsed_resume: Dict, top_k: int = 10) -> List[Dict]:
        """Return top-k company matches with percent score and matching features list."""
        companies = self._ensure_embeddings_loaded()
        if not companies:
            return []

        resume_emb = self._embed_resume(parsed_resume)

        # build company matrix
        comp_embs = []
        for c in companies:
            emb = c.get('embedding')
            if emb is None:
                # defensive: zero vector with same dimension as resume_emb
                comp_embs.append(np.zeros(len(resume_emb)))
            else:
                comp_embs.append(np.array(emb))

        comp_matrix = np.vstack(comp_embs)

        # cosine similarity (handle 1D vectors)
        sims = cosine_similarity([resume_emb], comp_matrix)[0]

        results = []
        resume_skills = set((parsed_resume.get('skills') or []))
        cgpa = parsed_resume.get('cgpa', 7) or 7
        grad_year = parsed_resume.get('graduation_year', 2025) or 2025
        skills_count = len(resume_skills)
        for c, sim in zip(companies, sims):
            # compute keyword overlap
            comp_skills = set([s.strip().lower() for s in (c.get('required_skills') or '').split(',') if s.strip()])
            overlap = list(sorted(resume_skills.intersection(comp_skills)))
            overlap_count = len(overlap)
            overlap_ratio = (overlap_count / (len(comp_skills) + 1)) if comp_skills else 0

            # Enhanced scoring logic with CGPA and skill bonuses
            min_cgpa = float(c.get('min_cgpa', 6.0))
            cgpa_bonus = 0.0
            skill_bonus = 0.0
            rf_score = 0.0  # Initialize RF score

            # CGPA bonus: if CGPA > min_cgpa, add significant bonus
            if cgpa > min_cgpa:
                cgpa_bonus = min(0.3, (cgpa - min_cgpa) * 0.1)  # Up to 30% bonus

            # Skill bonus: if at least 1 skill matches, add bonus
            if overlap_count > 0:
                skill_bonus = min(0.4, overlap_count * 0.1)  # Up to 40% bonus for multiple matches

            # Use Random Forest only (not combined with DT)
            if RF_MODEL and SCALER:
                features = [cgpa, grad_year, skills_count, overlap_count]
                features_scaled = SCALER.transform([features])
                if hasattr(RF_MODEL, 'predict_proba'):
                    rf_score = RF_MODEL.predict_proba(features_scaled)[0][1]  # probability of positive class
                else:
                    rf_score = RF_MODEL.predict(features_scaled)[0]  # regression score
                    rf_score = min(1.0, max(0.0, rf_score))  # clamp to 0-1

                # Apply bonuses to RF score
                final_score = rf_score + cgpa_bonus + skill_bonus
                final_score = min(1.0, final_score)  # Cap at 100%
            else:
                # Enhanced fallback: combine embedding, overlap, and bonuses
                base_score = 0.6 * float(sim) + 0.4 * float(overlap_ratio)
                final_score = base_score + cgpa_bonus + skill_bonus
                final_score = min(1.0, final_score)  # Cap at 100%

            percent = round(final_score * 100, 2)

            # Store RF score separately for display
            rf_score_value = rf_score

            results.append({
                'company_id': c['id'],
                'company_name': c['name'],
                'role': c.get('role', ''),
                'score_percent': percent,
                'rf_score': rf_score_value,
                'cosine': float(round(float(sim), 4)),
                'overlap_count': len(overlap),
                'matching_features': overlap
            })

        results = sorted(results, key=lambda x: x['score_percent'], reverse=True)
        # Return all results with scores for practice mode
        return results


# ------------------------- Convenience top-level functions -------------------------

def get_company_recommendations_for_student(email: str, top_k: int = 10) -> List[Dict]:
    """Load student's resume path from DB, parse it and return ranked companies."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT resume_path, skills FROM students WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return []

    resume_path, skills = row
    if resume_path and os.path.exists(resume_path):
        parsed = parse_resume(resume_path)
    else:
        # fallback: use skills column text
        parsed = {'skills': [s.strip().lower() for s in (skills or '').split(',') if s.strip()], 'raw_text': ''}

    matcher = CompanyMatcher(DB_PATH)
    return matcher.match_parsed_resume(parsed, top_k=top_k)


# Compatibility alias for routes.py
def get_company_recommendations(email: str, top_k: int = 10) -> List[Dict]:
    """Alias for get_company_recommendations_for_student (compatibility)"""
    return get_company_recommendations_for_student(email, top_k)


def precompute_all_company_embeddings():
    m = CompanyMatcher(DB_PATH)
    return m.precompute_company_embeddings()


# Make module runnable for quick checks
if __name__ == '__main__':
    print('Precomputing company embeddings...')
    n = precompute_all_company_embeddings()
    print(f'Done. {n} embeddings stored.')
