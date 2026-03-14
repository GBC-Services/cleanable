export interface RevenueByRegion {
  region: string;
  revenue: number;
  bookings: number;
  profit: number;
}

export interface MonthlyRevenue {
  month: string;
  revenue: number;
  costs: number;
  profit: number;
}

export interface FinancialSummary {
  total_revenue: number;
  total_costs: number;
  total_profit: number;
  total_bookings: number;
  avg_booking_value: number;
  profit_margin: number;
}

export interface CleaningPerformance {
  cleaner_name: string;
  completed: number;
  avg_score: number;
  revenue_generated: number;
}

export interface CompanyDetail {
  id: number;
  uuid: string;
  name: string;
  slug: string;
  phone: string;
  description: string;
  region: number | null;
  region_name: string;
  logo: string | null;
  logo_small: string | null;
  stripe_account_id: string | null;
  has_fees_accepted: boolean;
  created: string;
  updated: string;
}
