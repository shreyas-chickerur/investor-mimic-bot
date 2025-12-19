import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship

from .base import Base


class InvestorType(enum.Enum):
    RETAIL = "retail"
    INSTITUTIONAL = "institutional"
    FUND = "fund"


class TradeType(enum.Enum):
    BUY = "buy"
    SELL = "sell"


class Investor(Base):
    __tablename__ = "investors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    type = Column(Enum(InvestorType), default=InvestorType.RETAIL)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    portfolios = relationship("Portfolio", back_populates="investor")


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    investor_id = Column(Integer, ForeignKey("investors.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    investor = relationship("Investor", back_populates="portfolios")
    positions = relationship("Position", back_populates="portfolio")
    trades = relationship("Trade", back_populates="portfolio")


class Security(Base):
    __tablename__ = "securities"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True)
    name = Column(String)
    asset_class = Column(String)

    # Relationships
    positions = relationship("Position", back_populates="security")
    trades = relationship("Trade", back_populates="security")


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    security_id = Column(Integer, ForeignKey("securities.id"))
    quantity = Column(Float)
    average_cost = Column(Float)
    current_value = Column(Float)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    portfolio = relationship("Portfolio", back_populates="positions")
    security = relationship("Security", back_populates="positions")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    security_id = Column(Integer, ForeignKey("securities.id"))
    type = Column(Enum(TradeType))
    quantity = Column(Float)
    price = Column(Float)
    total_amount = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    portfolio = relationship("Portfolio", back_populates="trades")
    security = relationship("Security", back_populates="trades")
