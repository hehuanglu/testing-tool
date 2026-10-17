import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { register, toSafeApiFailure } from '../../api/auth';
import { useAuth } from '../../context/auth-context';
import divider from '../../assets/login/divider.svg';
import eyeOuter from '../../assets/login/eye-outer.svg';
import eyeInner from '../../assets/login/eye-inner.svg';
import googleBlue from '../../assets/login/google-blue.svg';
import googleGreen from '../../assets/login/google-green.svg';
import googleRed from '../../assets/login/google-red.svg';
import googleYellow from '../../assets/login/google-yellow.svg';

interface FieldErrors {
  fullName?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
}

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface PasswordFieldProps {
  id: string;
  label: string;
  value: string;
  error?: string;
  autoComplete: 'new-password';
  onChange: (value: string) => void;
}

function PasswordField({ id, label, value, error, autoComplete, onChange }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);
  const errorId = `${id}-error`;

  return (
    <div className="space-y-2">
      <label className="block text-base font-medium leading-6" htmlFor={id}>{label}</label>
      <div className="relative">
        <input
          id={id}
          autoComplete={autoComplete}
          className="h-12 w-full rounded-lg border border-[#d0d5dd] bg-transparent px-4 py-3 pr-12 text-base leading-6 outline-none placeholder:tracking-[4px] placeholder:text-[#999da3] focus:border-[#4b5768] focus:ring-2 focus:ring-[#299d91]"
          maxLength={72}
          placeholder="••••••••••••••"
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-describedby={error ? errorId : undefined}
          aria-invalid={error ? true : undefined}
        />
        <button
          aria-label={visible ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
          className="absolute right-4 top-3 h-6 w-6 rounded focus:outline-none focus:ring-2 focus:ring-[#299d91]"
          type="button"
          onClick={() => setVisible((current) => !current)}
        >
          <img alt="" className="absolute inset-0 h-6 w-6" src={eyeOuter} />
          {!visible && <img alt="" className="absolute inset-0 h-6 w-6" src={eyeInner} />}
        </button>
      </div>
      {error && <p id={errorId} className="text-sm text-[#e73d1c]">{error}</p>}
    </div>
  );
}

export function SignUpForm() {
  const navigate = useNavigate();
  const { completeLogin } = useAuth();
  const requestController = useRef<AbortController | null>(null);
  const isMounted = useRef(true);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState('');

  useEffect(() => () => {
    isMounted.current = false;
    requestController.current?.abort();
  }, []);

  function validate(): FieldErrors {
    const errors: FieldErrors = {};
    if (!fullName.trim()) errors.fullName = 'Full name is required.';
    if (!email.trim()) errors.email = 'Email is required.';
    else if (!emailPattern.test(email.trim())) errors.email = 'Enter a valid email address.';
    if (!password) errors.password = 'Password is required.';
    if (!confirmPassword) errors.confirmPassword = 'Confirm password is required.';
    else if (password !== confirmPassword) errors.confirmPassword = 'Passwords do not match.';
    return errors;
  }

  function clearFieldError(field: keyof FieldErrors): void {
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
    setFormError('');
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (isLoading) return;
    const errors = validate();
    setFieldErrors(errors);
    setFormError('');
    if (Object.keys(errors).length > 0) return;

    const controller = new AbortController();
    requestController.current?.abort();
    requestController.current = controller;
    setIsLoading(true);
    try {
      const result = await register({
        fullName: fullName.trim(),
        email: email.trim(),
        password,
        'confirm Password': confirmPassword,
      }, controller.signal);
      completeLogin(result.user, result.token, true);
      setPassword('');
      setConfirmPassword('');
      navigate('/', { replace: true });
    } catch (error: unknown) {
      if (!isMounted.current) return;
      const failure = toSafeApiFailure(error);
      if (failure.statusCode === 409 && failure.message === 'This email is already registered.') {
        setFieldErrors((current) => ({ ...current, email: failure.message }));
      } else if (failure.statusCode === 400 && failure.message === 'Passwords do not match.') {
        setFieldErrors((current) => ({ ...current, confirmPassword: failure.message }));
      } else {
        setFormError(failure.message || 'Unable to create your account. Please try again.');
      }
    } finally {
      if (requestController.current === controller) requestController.current = null;
      if (isMounted.current) setIsLoading(false);
    }
  }

  return (
    <form className="mt-10 w-full" noValidate onSubmit={(event) => void handleSubmit(event)}>
      <div className="space-y-5">
        <div className="space-y-2">
          <label className="block text-base font-medium leading-6" htmlFor="register-name">Name</label>
          <input
            id="register-name"
            autoComplete="name"
            className="h-12 w-full rounded-lg border border-[#4b5768] bg-transparent px-4 py-3 text-base leading-6 text-[#4b5768] outline-none placeholder:text-[#4b5768] focus:ring-2 focus:ring-[#299d91]"
            maxLength={120}
            placeholder="Tanzir Rahman"
            type="text"
            value={fullName}
            onChange={(event) => { setFullName(event.target.value); clearFieldError('fullName'); }}
            aria-describedby={fieldErrors.fullName ? 'register-name-error' : undefined}
            aria-invalid={fieldErrors.fullName ? true : undefined}
          />
          {fieldErrors.fullName && <p id="register-name-error" className="text-sm text-[#e73d1c]">{fieldErrors.fullName}</p>}
        </div>

        <div className="space-y-2">
          <label className="block text-base font-medium leading-6" htmlFor="register-email">Email Address</label>
          <input
            id="register-email"
            autoComplete="email"
            className="h-12 w-full rounded-lg border border-[#d0d5dd] bg-transparent px-4 py-3 text-base leading-6 outline-none placeholder:text-[#999da3] focus:border-[#4b5768] focus:ring-2 focus:ring-[#299d91]"
            inputMode="email"
            maxLength={254}
            placeholder="hello@example.com"
            type="email"
            value={email}
            onChange={(event) => { setEmail(event.target.value); clearFieldError('email'); }}
            aria-describedby={fieldErrors.email ? 'register-email-error' : undefined}
            aria-invalid={fieldErrors.email ? true : undefined}
          />
          {fieldErrors.email && <p id="register-email-error" className="text-sm text-[#e73d1c]">{fieldErrors.email}</p>}
        </div>

        <PasswordField id="register-password" label="Password" autoComplete="new-password" value={password} error={fieldErrors.password} onChange={(value) => { setPassword(value); clearFieldError('password'); clearFieldError('confirmPassword'); }} />
        <PasswordField id="register-confirm-password" label="Confirm Password" autoComplete="new-password" value={confirmPassword} error={fieldErrors.confirmPassword} onChange={(value) => { setConfirmPassword(value); clearFieldError('confirmPassword'); }} />
      </div>

      <p className="mt-6 text-sm leading-5 text-[#73809a]">
        By continuing, you agree to our <span aria-disabled="true" className="text-[#299d91]">terms of service.</span>
      </p>

      <button className="mt-5 flex h-12 w-full items-center justify-center rounded bg-[#299d91] px-3 py-4 text-base font-semibold leading-6 text-white focus:outline-none focus:ring-2 focus:ring-[#299d91] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70" disabled={isLoading} type="submit">
        {isLoading ? <span aria-label="Creating account" className="h-5 w-5 animate-spin rounded-full border-2 border-white border-r-transparent" /> : 'Sign up'}
      </button>
      {formError && <p role="alert" className="mt-3 text-center text-sm text-[#e73d1c]">{formError}</p>}

      <div className="relative mt-6 flex h-9 items-center justify-center">
        <img alt="" className="absolute left-[29px] top-[17px] h-px w-[342px]" src={divider} />
        <span className="relative bg-[#f4f5f7] px-2 text-sm leading-5 text-[#999da3]">or sign up with</span>
      </div>

      <button aria-disabled="true" className="mt-4 flex h-12 w-full cursor-default items-center justify-center gap-4 rounded bg-[#e4e7eb] px-[69px] py-3 text-base leading-6 text-[#4b5768]" type="button">
        <span aria-hidden="true" className="relative h-6 w-6 shrink-0">
          {[googleBlue, googleGreen, googleYellow, googleRed].map((asset) => <img alt="" className="absolute inset-0 h-6 w-6" key={asset} src={asset} />)}
        </span>
        <span className="whitespace-nowrap">Continue with Google</span>
      </button>

      <p className="mt-8 text-center text-base leading-6 text-[#999da3]">
        Already have an account? <Link className="font-semibold text-[#299d91] focus:outline-none focus:ring-2 focus:ring-[#299d91]" to="/login">Sign in here</Link>
      </p>
    </form>
  );
}
