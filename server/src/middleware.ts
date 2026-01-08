/**
 * Express Middleware
 * Security, rate limiting, and request handling middleware
 */

import { Request, Response, NextFunction, RequestHandler } from 'express';
import rateLimit from 'express-rate-limit';
import { RATE_LIMITS, LIMITS } from './constants.js';
import logger from './logger.js';

// Extend Express Request to include requestId
declare global {
  namespace Express {
    interface Request {
      requestId?: string;
    }
  }
}

/**
 * Generate a unique request ID
 */
function generateRequestId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Request ID middleware - adds unique ID to each request
 */
export const requestIdMiddleware: RequestHandler = (req, _res, next) => {
  req.requestId = req.headers['x-request-id'] as string || generateRequestId();
  next();
};

/**
 * Request logging middleware
 */
export const requestLoggingMiddleware: RequestHandler = (req, res, next) => {
  const startTime = Date.now();

  res.on('finish', () => {
    const duration = Date.now() - startTime;
    logger.request(req.method, req.path, res.statusCode, duration, {
      requestId: req.requestId,
      userAgent: req.headers['user-agent'],
      ip: req.ip,
    });
  });

  next();
};

/**
 * Security headers middleware (when helmet is not available)
 */
export const securityHeadersMiddleware: RequestHandler = (_req, res, next) => {
  // Prevent clickjacking
  res.setHeader('X-Frame-Options', 'DENY');
  // Prevent MIME type sniffing
  res.setHeader('X-Content-Type-Options', 'nosniff');
  // Enable XSS filter
  res.setHeader('X-XSS-Protection', '1; mode=block');
  // Referrer policy
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  // Content Security Policy
  res.setHeader('Content-Security-Policy', "default-src 'self'");

  next();
};

/**
 * Rate limiter for general API requests
 */
export const generalRateLimiter = rateLimit({
  windowMs: RATE_LIMITS.GENERAL.windowMs,
  max: RATE_LIMITS.GENERAL.max,
  message: { error: 'Too many requests, please try again later' },
  standardHeaders: true,
  legacyHeaders: false,
  handler: (req, res) => {
    logger.warn('Rate limit exceeded', {
      requestId: req.requestId,
      ip: req.ip,
      path: req.path,
    });
    res.status(429).json({ error: 'Too many requests, please try again later' });
  },
});

/**
 * Stricter rate limiter for authentication endpoints
 */
export const authRateLimiter = rateLimit({
  windowMs: RATE_LIMITS.AUTH.windowMs,
  max: RATE_LIMITS.AUTH.max,
  message: { error: 'Too many authentication attempts, please try again later' },
  standardHeaders: true,
  legacyHeaders: false,
  handler: (req, res) => {
    logger.warn('Auth rate limit exceeded', {
      requestId: req.requestId,
      ip: req.ip,
      path: req.path,
    });
    res.status(429).json({ error: 'Too many authentication attempts, please try again later' });
  },
});

/**
 * Rate limiter for SMS endpoints
 */
export const smsRateLimiter = rateLimit({
  windowMs: RATE_LIMITS.SMS.windowMs,
  max: RATE_LIMITS.SMS.max,
  message: { error: 'SMS rate limit exceeded, please try again later' },
  standardHeaders: true,
  legacyHeaders: false,
});

/**
 * Rate limiter for call endpoints
 */
export const callRateLimiter = rateLimit({
  windowMs: RATE_LIMITS.CALL.windowMs,
  max: RATE_LIMITS.CALL.max,
  message: { error: 'Call rate limit exceeded, please try again later' },
  standardHeaders: true,
  legacyHeaders: false,
});

/**
 * Error handling middleware
 */
export const errorHandlerMiddleware = (
  err: Error,
  req: Request,
  res: Response,
  _next: NextFunction
): void => {
  logger.error('Unhandled error', err, {
    requestId: req.requestId,
    path: req.path,
    method: req.method,
  });

  // Don't leak error details in production
  const message = process.env.NODE_ENV === 'production'
    ? 'Internal server error'
    : err.message;

  res.status(500).json({ error: message });
};

/**
 * 404 handler
 */
export const notFoundHandler: RequestHandler = (req, res) => {
  logger.warn('Route not found', {
    requestId: req.requestId,
    path: req.path,
    method: req.method,
  });
  res.status(404).json({ error: 'Not found' });
};

/**
 * Graceful shutdown handler
 */
export function setupGracefulShutdown(
  server: { close: (callback: () => void) => void },
  cleanup?: () => Promise<void> | void
): void {
  let isShuttingDown = false;

  const shutdown = async (signal: string) => {
    if (isShuttingDown) return;
    isShuttingDown = true;

    logger.info(`Received ${signal}, starting graceful shutdown...`);

    // Stop accepting new connections
    server.close(async () => {
      logger.info('HTTP server closed');

      // Run cleanup
      if (cleanup) {
        try {
          await cleanup();
          logger.info('Cleanup completed');
        } catch (error) {
          logger.error('Cleanup failed', error);
        }
      }

      logger.info('Shutdown complete');
      process.exit(0);
    });

    // Force shutdown after 30 seconds
    setTimeout(() => {
      logger.error('Forced shutdown after timeout');
      process.exit(1);
    }, 30000);
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
}
