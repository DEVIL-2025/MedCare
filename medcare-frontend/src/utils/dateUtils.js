/**
 * Centralized Date & Time Utility for MedCare Control Tower
 * Standardized to Asia/Kolkata (IST, UTC+05:30)
 */
import { useState, useEffect } from 'react';

export const IST_TIMEZONE = 'Asia/Kolkata';

/**
 * Parses any date/time input (ISO string, epoch timestamp, Date object) safely.
 */
export function parseDate(dateInput) {
  if (!dateInput) return null;
  if (dateInput instanceof Date) return isNaN(dateInput.getTime()) ? null : dateInput;
  if (typeof dateInput === 'number') return new Date(dateInput);
  if (typeof dateInput === 'string') {
    // If it is a date-only string like YYYY-MM-DD, parse as local calendar date
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateInput)) {
      const [y, m, d] = dateInput.split('-').map(Number);
      return new Date(y, m - 1, d);
    }
    // Parse ISO string
    const d = new Date(dateInput);
    return isNaN(d.getTime()) ? null : d;
  }
  return null;
}

/**
 * Formats a date + time in Asia/Kolkata (IST) timezone.
 * Example: "25 Aug 2026, 10:42 PM IST"
 */
export function formatDateTime(dateInput, options = {}) {
  const d = parseDate(dateInput);
  if (!d) return options.fallback || '-';

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
    const formatted = new Intl.DateTimeFormat('en-IN', { ...defaultOptions, ...options }).format(d);
    return options.hideZone ? formatted : `${formatted} IST`;
  } catch (err) {
    console.warn('formatDateTime error:', err);
    return d.toLocaleString('en-IN', { timeZone: IST_TIMEZONE });
  }
}

/**
 * Formats a date only in Asia/Kolkata (IST) timezone.
 * Example: "25 Aug 2026"
 */
export function formatDate(dateInput, options = {}) {
  const d = parseDate(dateInput);
  if (!d) return options.fallback || '-';

  const defaultOptions = {
    timeZone: IST_TIMEZONE,
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  };

  try {
    return new Intl.DateTimeFormat('en-IN', { ...defaultOptions, ...options }).format(d);
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
  if (!d) return options.fallback || '-';

  const defaultOptions = {
    timeZone: IST_TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
    second: options.includeSeconds !== false ? '2-digit' : undefined,
    hour12: true,
  };

  try {
    const formatted = new Intl.DateTimeFormat('en-IN', { ...defaultOptions, ...options }).format(d);
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
 * Calculates remaining days from now to target date in IST.
 */
export function getDaysToExpiry(expiryDateInput) {
  const d = parseDate(expiryDateInput);
  if (!d) return 999;
  const now = new Date();
  const diffTime = d.getTime() - now.getTime();
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
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
