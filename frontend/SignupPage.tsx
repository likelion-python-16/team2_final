import React, { useState } from 'react';
import { FileText, Check } from 'lucide-react';
import { useHealthNavigation } from '../HealthNavigation';
import { OAuthButton } from '../OAuthButton';
import { PasswordInput } from '../PasswordInput';
import { TestimonialCard } from '../TestimonialCard';
import { ThemeToggle } from '../ThemeToggle';

type OAuthProvider = 'kakao' | 'naver';

type FormErrors = {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
};

const INITIAL_ERRORS: FormErrors = {
  fullName: '',
  email: '',
  password: '',
  confirmPassword: '',
};

export function SignupPage() {
  const { setCurrentPage } = useHealthNavigation();
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState<FormErrors>(INITIAL_ERRORS);
  const [agreedToTerms, setAgreedToTerms] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsLoading(true);
    setErrors(INITIAL_ERRORS);

    const validationErrors: FormErrors = { ...INITIAL_ERRORS };

    if (!formData.fullName.trim()) {
      validationErrors.fullName = 'Full name is required';
    } else if (formData.fullName.trim().length < 2) {
      validationErrors.fullName = 'Name must be at least 2 characters';
    }

    if (!formData.email) {
      validationErrors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      validationErrors.email = 'Please enter a valid email address';
    }

    if (!formData.password) {
      validationErrors.password = 'Password is required';
    } else if (formData.password.length < 8) {
      validationErrors.password = 'Password must be at least 8 characters';
    } else if (!/(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/.test(formData.password)) {
      validationErrors.password = 'Password must contain uppercase, lowercase, and number';
    }

    if (!formData.confirmPassword) {
      validationErrors.confirmPassword = 'Please confirm your password';
    } else if (formData.password !== formData.confirmPassword) {
      validationErrors.confirmPassword = 'Passwords do not match';
    }

    if (
      validationErrors.fullName ||
      validationErrors.email ||
      validationErrors.password ||
      validationErrors.confirmPassword ||
      !agreedToTerms
    ) {
      setErrors(validationErrors);
      setIsLoading(false);
      return;
    }

    setTimeout(() => {
      setIsLoading(false);
      setCurrentPage('setup');
    }, 2000);
  };

  const handleOAuthSignup = (provider: OAuthProvider) => {
    console.log(`Sign up with ${provider}`);
    setTimeout(() => {
      setCurrentPage('setup');
    }, 1000);
  };

  const handleInputChange = (field: keyof typeof formData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: '' }));
    }
  };

  const passwordStrength = () => {
    const password = formData.password;
    let strength = 0;
    if (password.length >= 8) strength += 1;
    if (/[a-z]/.test(password)) strength += 1;
    if (/[A-Z]/.test(password)) strength += 1;
    if (/\d/.test(password)) strength += 1;
    if (/[^a-zA-Z\d]/.test(password)) strength += 1;
    return strength;
  };

  const getStrengthColor = (strength: number) => {
    if (strength <= 2) return 'bg-destructive';
    if (strength <= 3) return 'bg-warning';
    return 'bg-success';
  };

  const getStrengthText = (strength: number) => {
    if (strength <= 2) return 'Weak';
    if (strength <= 3) return 'Good';
    return 'Strong';
  };

  return (
    <div className="auth-container">
      <div className="grid lg:grid-cols-2 min-h-screen">
        <div className="auth-panel">
          <div className="auth-form">
            <div className="flex justify-center mb-8">
              <div className="w-12 h-12 bg-primary rounded-xl flex items-center justify-center">
                <span className="text-primary-foreground font-bold text-xl">H</span>
              </div>
            </div>

            <div className="auth-header mb-8">
              <h1 className="auth-title text-3xl">Create your account</h1>
              <p className="auth-subtitle">Start your personalized health journey</p>
            </div>

            <div className="space-y-3 mb-6">
              <OAuthButton provider="kakao" onClick={() => handleOAuthSignup('kakao')} />
              <OAuthButton provider="naver" onClick={() => handleOAuthSignup('naver')} />
            </div>

            <div className="oauth-divider mb-6">
              <span>or</span>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="fullName" className="block text-sm font-medium">
                  Full Name
                </label>
                <input
                  id="fullName"
                  type="text"
                  value={formData.fullName}
                  onChange={(event) => handleInputChange('fullName', event.target.value)}
                  placeholder="Enter your full name"
                  required
                  className={`auth-input ${errors.fullName ? 'border-destructive focus:border-destructive focus:ring-destructive/20' : ''}`}
                />
                {errors.fullName && <p className="text-sm text-destructive">{errors.fullName}</p>}
              </div>

              <div className="space-y-2">
                <label htmlFor="email" className="block text-sm font-medium">
                  Email Address
                </label>
                <input
                  id="email"
                  type="email"
                  value={formData.email}
                  onChange={(event) => handleInputChange('email', event.target.value)}
                  placeholder="Enter your email"
                  required
                  className={`auth-input ${errors.email ? 'border-destructive focus:border-destructive focus:ring-destructive/20' : ''}`}
                />
                {errors.email && <p className="text-sm text-destructive">{errors.email}</p>}
              </div>

              <div className="space-y-2">
                <label htmlFor="password" className="block text-sm font-medium">
                  Password
                </label>
                <PasswordInput
                  value={formData.password}
                  onChange={(value) => handleInputChange('password', value)}
                  placeholder="Create a strong password"
                  required
                  error={errors.password}
                />

                {formData.password && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className={`h-full transition-all duration-300 ${getStrengthColor(passwordStrength())}`}
                          style={{ width: `${(passwordStrength() / 5) * 100}%` }}
                        />
                      </div>
                      <span
                        className={`text-xs font-medium ${
                          passwordStrength() <= 2
                            ? 'text-destructive'
                            : passwordStrength() <= 3
                            ? 'text-warning'
                            : 'text-success'
                        }`}
                      >
                        {getStrengthText(passwordStrength())}
                      </span>
                    </div>

                    <div className="space-y-1 text-xs">
                      <div
                        className={`flex items-center gap-2 ${
                          formData.password.length >= 8
                            ? 'text-success'
                            : 'text-muted-foreground'
                        }`}
                      >
                        <Check
                          className={`w-3 h-3 ${
                            formData.password.length >= 8 ? 'opacity-100' : 'opacity-30'
                          }`}
                        />
                        At least 8 characters
                      </div>
                      <div
                        className={`flex items-center gap-2 ${
                          /[A-Z]/.test(formData.password) && /[a-z]/.test(formData.password)
                            ? 'text-success'
                            : 'text-muted-foreground'
                        }`}
                      >
                        <Check
                          className={`w-3 h-3 ${
                            /[A-Z]/.test(formData.password) && /[a-z]/.test(formData.password)
                              ? 'opacity-100'
                              : 'opacity-30'
                          }`}
                        />
                        Upper and lowercase letters
                      </div>
                      <div
                        className={`flex items-center gap-2 ${
                          /\d/.test(formData.password)
                            ? 'text-success'
                            : 'text-muted-foreground'
                        }`}
                      >
                        <Check
                          className={`w-3 h-3 ${
                            /\d/.test(formData.password) ? 'opacity-100' : 'opacity-30'
                          }`}
                        />
                        At least one number
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <label htmlFor="confirmPassword" className="block text-sm font-medium">
                  Confirm Password
                </label>
                <PasswordInput
                  value={formData.confirmPassword}
                  onChange={(value) => handleInputChange('confirmPassword', value)}
                  placeholder="Confirm your password"
                  required
                  error={errors.confirmPassword}
                />
              </div>

              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <div className="flex items-center h-5">
                    <input
                      id="terms"
                      type="checkbox"
                      checked={agreedToTerms}
                      onChange={(event) => setAgreedToTerms(event.target.checked)}
                      className="h-4 w-4 rounded border-border text-primary focus:ring-primary/20"
                    />
                  </div>
                  <label htmlFor="terms" className="text-sm text-muted-foreground leading-5">
                    I agree to the{' '}
                    <a href="#" className="auth-link">
                      Terms of Service
                    </a>
                    {' '}and{' '}
                    <a href="#" className="auth-link">
                      Privacy Policy
                    </a>
                  </label>
                </div>

                {!agreedToTerms &&
                  (errors.fullName || errors.email || errors.password || errors.confirmPassword) && (
                    <p className="text-sm text-destructive">You must agree to the terms to continue</p>
                  )}
              </div>

              <button
                type="submit"
                disabled={isLoading || !agreedToTerms}
                className="auth-button-primary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <div className="flex items-center justify-center gap-2">
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Creating account...
                  </div>
                ) : (
                  'Create Account'
                )}
              </button>
            </form>

            <p className="text-center text-sm text-muted-foreground mt-6">
              Already have an account?{' '}
              <button onClick={() => setCurrentPage('login')} className="auth-link font-medium">
                Sign in
              </button>
            </p>
          </div>
        </div>

        <div className="hidden lg:block relative">
          <TestimonialCard
            quote="The AI-powered workout plans adapted perfectly to my fitness level and goals. I've seen incredible results in just 8 weeks!"
            author="Marcus Rodriguez"
            handle="@marcusfit"
          />

          <div className="absolute top-8 right-8 flex items-center gap-4">
            <ThemeToggle />
            <a
              href="#"
              className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
            >
              <FileText className="w-5 h-5" />
              <span className="text-sm font-medium">Documentation</span>
            </a>
          </div>
        </div>
      </div>

      <div className="lg:hidden bg-muted/30 border-t border-border">
        <div className="px-8 py-6">
          <div className="flex items-center justify-between mb-4">
            <ThemeToggle />
            <a
              href="#"
              className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
            >
              <FileText className="w-4 h-4" />
              <span className="text-sm">Docs</span>
            </a>
          </div>
          <div className="text-center">
            <p className="text-foreground font-medium mb-2">
              "The AI-powered workout plans adapted perfectly to my fitness level and goals."
            </p>
            <p className="text-sm text-muted-foreground">— Marcus Rodriguez, @marcusfit</p>
          </div>
        </div>
      </div>
    </div>
  );
}
