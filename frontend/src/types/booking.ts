/**
 * Booking domain types — mirror the Django API exactly.
 */

export interface Place {
  id: number;
  uuid: string;
  name: string;
  type: number;
  type_display: string;
  address: string;
  apartment_nmb: string;
  full_address: string;
  bedrooms_nmb: number | null;
  bathrooms_nmb: number | null;
  area_size: number | null;
  region: number | null;
  region_name: string;
  city: number | null;
  state: number | null;
  zip_code: number | null;
}

export interface Service {
  id: number;
  uuid: string;
  name: string;
  slug: string;
  description: string;
  apartment_plan: number | null;
  apartment_plan_name: string;
  cleaning_type: number | null;
  cleaning_type_name: string;
  regularity_type: number;
  regularity_type_display: string;
  is_area_based_fee: boolean;
  is_chore: boolean;
  checklist: string | null;
}

export interface ServiceFee {
  id: number;
  service: number;
  service_name: string;
  service_uuid: string;
  client_fee: string;
  is_area_based: boolean;
}

export interface BookingService {
  id: number;
  service: number;
  service_name: string;
  service_uuid: string;
  service_fee: number;
  fee: string;
  company_fee: string;
}

export interface Booking {
  id: number;
  uuid: string;
  short_id: number;
  status: number;
  status_display: string;
  payment_status: number;
  payment_status_display: string;
  place: number;
  place_address: string;
  scheduled_date: string;
  scheduled_range: string;
  service_names: string;
  total_fee: string;
  discount_amount: string;
  total_fee_final: string;
  regularity_type: number;
  created: string;
}

export interface BookingDetail extends Booking {
  client: number;
  client_email: string;
  place_detail: Place;
  services: BookingService[];
  bedrooms_nmb: number | null;
  bathrooms_nmb: number | null;
  area_size: number | null;
  scheduled_start_dt: string;
  scheduled_end_dt: string;
  regularity_option: number | null;
  comments: string;
  special_request: string;
  tip_amount: string;
  is_tip_paid: boolean;
  total_costs: string;
  profit: string;
  stripe_payment_intent_id: string | null;
  next_cleaning: {
    id: number;
    uuid: string;
    status: number;
    status_display: string;
    scheduled_date: string;
  } | null;
  updated: string;
  client_secret?: string;
}

export interface BookingCreatePayload {
  place_id: number;
  service_fee_ids: number[];
  scheduled_date: string;
  scheduled_start_time: string;
  scheduled_end_time: string;
  regularity_type?: number;
  regularity_option?: number | null;
  comments?: string;
  special_request?: string;
  discount_code?: string;
}

// Location types
export interface Country {
  id: number;
  name: string;
  slug: string;
}

export interface State {
  id: number;
  name: string;
  slug: string;
  country: number;
  country_name: string;
}

export interface City {
  id: number;
  name: string;
  slug: string;
  state: number;
  state_name: string;
}

export interface ZipCode {
  id: number;
  value: string;
  city: number;
  city_name: string;
}

export interface Region {
  id: number;
  name: string;
  slug: string;
  profit_rate: string;
}

// Paginated list wrapper from Django REST Framework
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
