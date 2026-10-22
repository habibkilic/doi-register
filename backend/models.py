import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(120), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    password_hash = Column(String(200), nullable=True)
    academic_title = Column(String(50), default="Prof. Dr.")
    institution = Column(String(150), default="Üniversite")
    token_balance = Column(Integer, default=10)  # Her kullanıcıya 10 kredi hediye
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    journals = relationship("Journal", back_populates="owner")
    transactions = relationship("TokenTransaction", back_populates="user")


class Journal(Base):
    __tablename__ = "journals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(200), nullable=False)
    issn = Column(String(20), nullable=True)
    e_issn = Column(String(20), nullable=True)
    publisher = Column(String(150), nullable=True)
    website_url = Column(String(255), nullable=True)
    doi_prefix = Column(String(50), default="10.55555")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="journals")
    evaluations = relationship("Evaluation", back_populates="journal")
    articles = relationship("Article", back_populates="journal")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, index=True)
    journal_id = Column(Integer, ForeignKey("journals.id"), nullable=False)
    overall_score = Column(Float, default=0.0)
    doaj_score = Column(Float, default=0.0)
    tr_dizin_score = Column(Float, default=0.0)
    scopus_score = Column(Float, default=0.0)
    wos_score = Column(Float, default=0.0)
    copernicus_score = Column(Float, default=0.0)
    raw_text = Column(Text, nullable=True)
    full_report_json = Column(Text, nullable=False)  # JSON dökümü
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    journal = relationship("Journal", back_populates="evaluations")


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    journal_id = Column(Integer, ForeignKey("journals.id"), nullable=False)
    title = Column(String(300), nullable=False)
    authors = Column(String(300), nullable=False)
    abstract = Column(Text, nullable=True)
    volume = Column(String(20), default="1")
    issue = Column(String(20), default="1")
    publication_year = Column(Integer, default=datetime.datetime.utcnow().year)
    first_page = Column(String(10), default="1")
    last_page = Column(String(10), default="10")
    doi_number = Column(String(100), nullable=True, unique=True)
    status = Column(String(30), default="pending")  # pending, registered, failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    journal = relationship("Journal", back_populates="articles")
    doi_requests = relationship("DoiRequest", back_populates="article")


class DoiRequest(Base):
    __tablename__ = "doi_requests"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    provider = Column(String(30), default="crossref_sandbox")  # crossref_sandbox, zenodo
    status = Column(String(30), default="submitted")  # submitted, success, error
    response_doi = Column(String(120), nullable=True)
    request_payload = Column(Text, nullable=True)
    response_log = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    article = relationship("Article", back_populates="doi_requests")


class TokenTransaction(Base):
    __tablename__ = "token_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tokens = Column(Integer, nullable=False)
    amount_paid = Column(Float, default=0.0)
    currency = Column(String(10), default="TRY")
    payment_method = Column(String(30), default="iyzico_card")  # iyzico_card, wire_transfer
    status = Column(String(30), default="completed")  # completed, pending_approval, failed
    reference_code = Column(String(50), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="transactions")
