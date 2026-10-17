import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { login, toSafeApiFailure } from '../../api/auth';
import { useAuth } from '../../context/auth-context';
import checkIcon from '../../assets/login/check.svg';
import divider from '../../assets/login/divider.svg';
import eyeOuter from '../../assets/login/eye-outer.svg';
import eyeInner from '../../assets/login/eye-inner.svg';
import googleBlue from '../../assets/login/google-blue.svg';
import googleGreen from '../../assets/login/google-green.svg';
import googleRed from '../../assets/login/google-red.svg';
import googleYellow from '../../assets/login/google-yellow.svg';

interface FieldErrors {
  email?: string;
  password?: string;
}

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function LoginForm() {
  const navigate = useNavigate();
  const { completeLogin } = useAuth();
  const requestController = useRef<AbortController | null>(null);
  const isMounted = useRef(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState('');

  useEffect(() => () => {
    isMounted.current = false;
    requestController.current?.abort();
  }, []);

  function validate(): FieldErrors {
    const errors: FieldErrors = {};
    if (!email.trim()) errors.email = 'Email is required.';
    else if (!emailPattern.test(email.trim())) errors.email = 'Enter a valid email address.';
    if (!password) errors.password = 'Password is required.';
    return errors;
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
      const result = await login({ email: email.trim(), password }, controller.signal);
      completeLogin(result.user, result.accessToken, rememberMe);
      setPassword('');
      navigate('/', { replace: true });
    } catch (error: unknown) {
      if (!isMounted.current) return;
      const failure = toSafeApiFailure(error);
      setFormError(failure.statusCode === 401 ? 'Incorrect email or password.' : failure.message);
    } finally {
      if (requestController.current === controller) requestController.current = null;
      if (isMounted.current) setIsLoading(false);
    }
  }

  return (
    <form className="mt-16 w-full" noValidate onSubmit={(event) => void handleSubmit(event)}>
      <div className="space-y-6">
        <div className="space-y-2">
          <label className="block text-base font-medium leading-6" htmlFor="login-email">Email Address</label>
          <input
            id="login-email"
            autoComplete="email"
            className="h-12 w-full rounded-lg border border-[#4b5768] bg-transparent px-4 py-3 text-base leading-6 text-[#4b5768] outline-none placeholder:text-[#4b5768] focus:ring-2 focus:ring-[#299d91]"
            inputMode="email"
            maxLength={254}
            placeholder="johndoe@email.com"
            type="email"
            value={email}
            onChange={(event) => { setEmail(event.target.value); setFieldErrors((current) => ({ ...current, email: undefined })); setFormError(''); }}
            aria-describedby={fieldErrors.email ? 'login-email-error' : undefined}
            aria-invalid={fieldErrors.email ? true : undefined}
          />
          {fieldErrors.email && <p id="login-email-error" className="text-sm text-[#e73d1c]">{fieldErrors.email}</p>}
        </div>

        <div className="space-y-2">
          <div className="flex h-6 items-center justify-between">
            <label className="text-base font-medium leading-6" htmlFor="login-password">Password</label>
            <span aria-disabled="true" className="text-xs leading-4 text-[#299d91]">Forgot Password?</span>
          </div>
          <div className="relative">
            <input
              id="login-password"
              autoComplete="current-password"
              className="h-12 w-full rounded-lg border border-[#d0d5dd] bg-transparent px-4 py-3 pr-12 text-base leading-6 outline-none placeholder:tracking-[4px] placeholder:text-[#999da3] focus:border-[#4b5768] focus:ring-2 focus:ring-[#299d91]"
              maxLength={72}
              placeholder="••••••••••••••"
              type="password"
              value={password}
              onChange={(event) => { setPassword(event.target.value); setFieldErrors((current) => ({ ...current, password: undefined })); setFormError(''); }}
              aria-describedby={fieldErrors.password ? 'login-password-error' : undefined}
              aria-invalid={fieldErrors.password ? true : undefined}
            />
            <span aria-hidden="true" className="pointer-events-none absolute right-4 top-3 h-6 w-6">
              <img alt="" className="absolute inset-0 h-6 w-6" src={eyeOuter} />
              <img alt="" className="absolute inset-0 h-6 w-6" src={eyeInner} />
            </span>
          </div>
          {fieldErrors.password && <p id="login-password-error" className="text-sm text-[#e73d1c]">{fieldErrors.password}</p>}
        </div>
      </div>

      <div className="mt-8 space-y-4">
        <label className="flex cursor-pointer items-center gap-4 text-base font-light leading-6">
          <input className="peer sr-only" type="checkbox" checked={rememberMe} onChange={(event) => setRememberMe(event.target.checked)} />
          <span className="flex h-5 w-5 items-center justify-center rounded-sm border border-[#299d91] peer-focus:ring-2 peer-focus:ring-[#299d91] peer-focus:ring-offset-2">
            {rememberMe && <img alt="" className="h-5 w-5" src={checkIcon} />}
          </span>
          Keep me signed in
        </label>
        <button className="flex h-12 w-full items-center justify-center rounded bg-[#299d91] px-3 py-4 text-base font-semibold leading-6 text-white focus:outline-none focus:ring-2 focus:ring-[#299d91] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70" disabled={isLoading} type="submit">
          {isLoading ? <span aria-label="Signing in" className="h-5 w-5 animate-spin rounded-full border-2 border-white border-r-transparent" /> : 'Login'}
        </button>
        {formError && <p role="alert" className="text-center text-sm text-[#e73d1c]">{formError}</p>}
      </div>

      <div className="relative mt-6 flex h-9 items-center justify-center">
        <img alt="" className="absolute left-[29px] top-[17px] h-px w-[342px]" src={divider} />
        <span className="relative bg-[#f4f5f7] px-2 text-sm leading-5 text-[#999da3]">or sign in with</span>
      </div>

      <button aria-disabled="true" className="mt-4 flex h-12 w-full cursor-default items-center justify-center gap-4 rounded bg-[#e4e7eb] px-[69px] py-3 text-base leading-6 text-[#4b5768]" type="button">
        <span aria-hidden="true" className="relative h-6 w-6 shrink-0">
          {[googleBlue, googleGreen, googleYellow, googleRed].map((asset) => <img alt="" className="absolute inset-0 h-6 w-6" key={asset} src={asset} />)}
        </span>
        <span className="whitespace-nowrap">Continue with Google</span>
      </button>

      <Link className="mt-10 block h-6 w-full text-center text-base font-semibold leading-6 text-[#299d91] focus:outline-none focus:ring-2 focus:ring-[#299d91]" to="/register">Create an account</Link>
    </form>
  );
}
