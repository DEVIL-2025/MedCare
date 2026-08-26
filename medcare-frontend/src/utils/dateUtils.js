/**
 * Centralized Date & Time Utility for MedCare Control Tower
 * Standardized to Asia/Kolkata (IST, UTC+05:30)
 */
import { useState, useEffect } from 'react';

export const IST_TIMEZONE = 'Asia/Kolkata';

/**
 * Clean custom configuration options before passing to Intl.DateTimeFormat.
 */
function sanitizeIntlOptions(options = {}) {
  const { hideZone, fallback, includeSeconds, ...intlOptions } = options;
  return intlOptions;
}

/**
 * Parses any date/time input (ISO string, epoch timestamp, Date object) safely.
 */
export function parseDate(dateInput) {
  if (!dateInput) return null;
  if (dateInput instanceof Date) return isNaN(dateInput.getTime()) ? null : dateInput;
  if (typeof dateInput === 'number') return new Date(dateInput);
  if (typeof dateInput === 'string') {
    const s = dateInput.trim();
    if (!s) return null;

    // If it is a date-only string like YYYY-MM-DD, parse as UTC midnight to avoid local timezone shifts
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
      const [y, m, d] = s.split('-').map(Number);
      return new Date(Date.UTC(y, m - 1, d));
    }

    // If string already has a timezone indicator (Z, +05:30, -04:00, etc.)
    if (/([+-]\d{2}:\d{2}|Z)$/i.test(s)) {
      const d = new Date(s);
      return isNaN(d.getTime()) ? null : d;
    }

    // If string is an ISO format with 'T' but no timezone offset, assume UTC timestamp from server
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(s)) {
      const d = new Date(s + 'Z');
      if (!isNaN(d.getTime())) return d;
    }

    // Standard date parsing fallback
    const d = new Date(s);
    return isNaN(d.getTime()) ? null : d;
  }
  return null;
}

/**
 * Formats a date + time in Asia/Kolkata (IST) timezone.
 * Example: "26 Aug 2026, 06:25 PM IST"
 */
export function formatDateTime(dateInput, options = {}) {
  if (typeof dateInput === 'string' && dateInput.includes('IST')) {
    return options.hideZone ? dateInput.replace(/\s+IST$/i, '') : dateInput;
  }

  const d = parseDate(dateInput);
  if (!d) return options.fallback || (typeof dateInput === 'string' ? dateInput : '-');

  const defaultOptions = {
    timeZone: IST_TIMEZONE,
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: options.includeSeconds ? '2-digit' : undefined,
    hour12: true,
  };

  try {
    const formatted = new Intl.DateTimeFormat(
      'en-IN',
      { ...defaultOptions, ...sanitizeIntlOptions(options) }
    ).format(d);
    return options.hideZone ? formatted : `${formatted} IST`;
  } catch (err) {
    console.warn('formatDateTime error:', err);
    return d.toLocaleString('en-IN', { timeZone: IST_TIMEZONE });
  }
}

/**
 * Formats a date only in Asia/Kolkata (IST) timezone.
 * Example: "26 Aug 2026"
 */
export function formatDate(dateInput, options = {}) {
  const d = parseDate(dateInput);
  if (!d) return options.fallback || (typeof dateInput === 'string' ? dateInput : '-');

  const defaultOptions = {
    timeZone: IST_TIMEZONE,
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  };

  try {
    return new Intl.DateTimeFormat(
      'en-IN',
      { ...defaultOptions, ...sanitizeIntlOptions(options) }
    ).format(d);
  } catch (err) {
    return d.toLocaleDateString('en-IN', { timeZone: IST_TIMEZONE });
  }
}

/**
 * Formats a time only in Asia/Kolkata (IST) timezone.
 * Example: "10:42:15 PM IST"
 */
export function formatTime(dateInput, options = {}) {
  const d = parseDate(dateInput);
  if (!d) return options.fallback || (typeof dateInput === 'string' ? dateInput : '-');

  const defaultOptions = {
    timeZone: IST_TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
    second: options.includeSeconds !== false ? '2-digit' : undefined,
    hour12: true,
  };

  try {
    const formatted = new Intl.DateTimeFormat(
      'en-IN',
      { ...defaultOptions, ...sanitizeIntlOptions(options) }
    ).format(d);
    return options.hideZone ? formatted : `${formatted} IST`;
  } catch (err) {
    return d.toLocaleTimeString('en-IN', { timeZone: IST_TIMEZONE });
  }
}

/**
 * Formats a relative time string (e.g. "2 min ago", "in 3 days").
 */
export function formatRelativeTime(dateInput) {
  const d = parseDate(dateInput);
  if (!d) return '-';

  const now = new Date();
  const diffSec = Math.round((d.getTime() - now.getTime()) / 1000);
  const diffMin = Math.round(diffSec / 60);
  const diffHours = Math.round(diffMin / 60);
  const diffDays = Math.round(diffHours / 24);

  if (Math.abs(diffSec) < 45) return 'just now';
  if (Math.abs(diffMin) < 60) {
    return diffMin > 0 ? `in ${diffMin} min` : `${Math.abs(diffMin)} min ago`;
  }
  if (Math.abs(diffHours) < 24) {
    return diffHours > 0 ? `in ${diffHours} hr` : `${Math.abs(diffHours)} hr ago`;
  }
  if (Math.abs(diffDays) < 30) {
    return diffDays > 0 ? `in ${diffDays} days` : `${Math.abs(diffDays)} days ago`;
  }
  return formatDate(d);
}

/**
 * Calculates remaining days from today to target date in calendar days.
 */
export function getDaysToExpiry(expiryDateInput) {
  const d = parseDate(expiryDateInput);
  if (!d) return 999;
  
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const targetDate = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  
  const diffTime = targetDate.getTime() - startOfToday.getTime();
  return Math.round(diffTime / (1000 * 60 * 60 * 24));
}

/**
 * React Hook for live updating current IST clock.
 */
export function useLiveISTClock(intervalMs = 1000) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = setInterval(() => {
      setNow(new Date());
    }, intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);

  return {
    now,
    dateString: formatDate(now),
    timeString: formatTime(now),
    dateTimeString: formatDateTime(now),
    shortTimeString: formatTime(now, { includeSeconds: false }),
  };
}