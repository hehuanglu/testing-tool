import axios from 'axios';
import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { listAccounts, type BankAccount } from '../api/accounts';
import { useAuth } from '../context/auth-context';
import { AccountEditForm } from '../components/accounts/AccountEditForm';
import { DeleteAccountModal } from '../components/accounts/DeleteAccountModal';
import imgVector from '../assets/accounts/asset-001.svg';
import imgVector1 from '../assets/accounts/asset-002.svg';
import imgMastercardLogo1 from '../assets/accounts/asset-003.png';
import imgVisaLogo1 from '../assets/accounts/asset-004.png';
import imgImage from '../assets/accounts/asset-005.png';
import imgVector2 from '../assets/accounts/asset-006.svg';
import imgChevronsRight from '../assets/accounts/asset-007.svg';
import imgClarityNotificationSolidBadged from '../assets/accounts/asset-008.svg';
import imgVector3 from '../assets/accounts/asset-009.svg';
import imgVector4 from '../assets/accounts/asset-010.svg';
import imgVector5 from '../assets/accounts/asset-011.svg';
import imgVector6 from '../assets/accounts/asset-012.svg';
import imgVector7 from '../assets/accounts/asset-013.svg';
import imgVector8 from '../assets/accounts/asset-014.svg';
import imgVector9 from '../assets/accounts/asset-015.svg';
import imgVector10 from '../assets/accounts/asset-016.svg';
import imgGroup from '../assets/accounts/asset-017.svg';
import imgVector11 from '../assets/accounts/asset-018.svg';
import imgVector12 from '../assets/accounts/asset-019.svg';
import imgVector13 from '../assets/accounts/asset-020.svg';
import imgVector14 from '../assets/accounts/asset-021.svg';
import imgVector15 from '../assets/accounts/asset-022.svg';
import imgVector16 from '../assets/accounts/asset-023.svg';
import imgVector17 from '../assets/accounts/asset-024.svg';
import imgVector18 from '../assets/accounts/asset-025.svg';
import imgIcon from '../assets/accounts/asset-026.svg';

function Search({ className }: { className?: string }) {
  return (
    <div className={className || "overflow-clip relative size-[24px]"} data-node-id="54:2473" data-name="search">
      <div className="absolute inset-[12.5%_20.83%_20.83%_12.5%]" data-node-id="54:2470" data-name="Vector">
        <div className="absolute inset-[-6.25%]">
          <img alt="" className="block max-w-none size-full" src={imgVector} />
        </div>
      </div>
      <div className="absolute inset-[69.37%_12.5%_12.5%_69.37%]" data-node-id="54:2471" data-name="Vector">
        <div className="absolute inset-[-22.99%]">
          <img alt="" className="block max-w-none size-full" src={imgVector1} />
        </div>
      </div>
    </div>
  );
}

function Mastercard({ className }: { className?: string }) {
  return (
    <div className={className || "h-[32px] overflow-clip relative w-[48px]"} data-node-id="408:5979" data-name="Mastercard">
      <div className="absolute h-[24px] left-[3px] top-[4px] w-[43px]" data-node-id="408:5989" data-name="Mastercard-Logo 1">
        <img alt="" className="absolute inset-0 max-w-none object-cover pointer-events-none size-full" src={imgMastercardLogo1} />
      </div>
    </div>
  );
}

const cardNodeIds = ['410:5376', '410:5354', '410:5421', '410:5492', '410:5469'];
const safeSystemError = 'A system error has occurred, please try again later.';
function formatBalance(value: number): string {
  return `$${new Intl.NumberFormat('en-US', { useGrouping: false, maximumFractionDigits: 4 }).format(value)}`;
}
export function AccountListPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const routeMessage = typeof location.state === 'object' && location.state !== null && 'message' in location.state && typeof location.state.message === 'string'
    ? location.state.message
    : '';
  const [accounts, setAccounts] = useState<BankAccount[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAccount, setSelectedAccount] = useState<BankAccount | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [accountToDelete, setAccountToDelete] = useState<BankAccount | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setAccounts([]);
    setError(null);
    setIsLoading(true);
    async function fetchAccounts(): Promise<void> {
      try {
        const result = await listAccounts(controller.signal);
        if (active) { setAccounts(result.accounts); setError(null); }
      } catch (failure: unknown) {
        if (!active || axios.isCancel(failure)) return;
        setAccounts([]);
        if (axios.isAxiosError(failure) && failure.response?.status === 401) {
          logout();
          navigate('/login', { replace: true, state: { sessionMessage: 'Please log in again.' } });
        } else setError(safeSystemError);
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void fetchAccounts();
    return () => { active = false; controller.abort(); };
  }, [logout, navigate]);
  return (
    <div className="bg-[#f4f5f7] relative min-h-[1024px] min-w-[1440px]" style={{ minHeight: Math.max(1024, 184 + Math.ceil((accounts.length + 1) / 3) * 320) }} data-node-id="66:5320" data-name="105. Balances">
      <section className="absolute left-[304px] top-[104px] right-[32px] flex flex-col gap-4" aria-labelledby="accounts-heading" data-node-id="410:5547">
        <h1 id="accounts-heading" className="text-[22px] font-normal leading-8 text-[#878787]" data-node-id="66:5347">Balances</h1>
        {routeMessage && <p role="alert" className="rounded-md bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800">{routeMessage}</p>}
        {successMessage && <p role="status" className="rounded-md bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">{successMessage}</p>}
        {selectedAccount ? (
          isEditing ? <AccountEditForm account={selectedAccount} onCancel={() => setIsEditing(false)} onUpdated={(updated) => {
            setAccounts((current) => current.map((item) => item.id === updated.id ? updated : item));
            setSelectedAccount(updated);
            setIsEditing(false);
            setSuccessMessage('Update successful');
          }} /> : <AccountDetailsPanel account={selectedAccount} onBack={() => { setSelectedAccount(null); setSuccessMessage(''); }} onEdit={() => { setSuccessMessage(''); setIsEditing(true); }} onDelete={() => { setSuccessMessage(''); setAccountToDelete(selectedAccount); }} />
        ) : isLoading ? <div role="status" aria-label="Loading accounts" className="grid grid-cols-3 gap-x-6 gap-y-8">{Array.from({ length: 5 }, (_, index) => <div key={index} className="h-72 animate-pulse rounded-lg bg-white p-6"><div className="h-11 border-b border-[#e8e8e8]"/><div className="mt-6 h-5 w-48 rounded bg-[#e8e8e8]"/><div className="mt-12 h-5 w-24 rounded bg-[#e8e8e8]"/></div>)}</div>
        : error ? <p role="alert" className="rounded-lg bg-white p-6 text-[#666]">{error}</p>
        : <div className="grid grid-cols-3 gap-x-6 gap-y-8" data-node-id="410:5546">
            {accounts.length === 0 && <p className="col-span-3 rounded-lg bg-white p-6 text-[#666]">You haven't linked any accounts. Please add an account,</p>}
            {accounts.map((account, index) => <AccountCard key={account.id} account={account} index={index} onDetails={() => navigate(`/accounts/${encodeURIComponent(String(account.id))}`)} onRemove={() => { setSuccessMessage(''); setAccountToDelete(account); }} />)}
            <AddAccountCard />
          </div>}
      </section>
      <div className="absolute border-[#e8e8e8] border-b border-solid content-stretch flex items-center justify-between left-[280px] pl-[24px] pr-[32px] py-[20px] top-0 w-[1160px]" data-node-id="411:6111" data-name="Header">
        <div className="content-stretch flex gap-[24px] items-center relative shrink-0" data-node-id="I411:6111;411:6047" data-name="Header">
          <div className="content-stretch flex gap-[4px] items-center relative shrink-0" data-node-id="I411:6111;411:6049" data-name="Date">
            <div className="relative shrink-0 size-[24px]" data-node-id="I411:6111;411:6050" data-name="chevrons-right">
              <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgChevronsRight} />
            </div>
            <p className="[word-break:break-word]  font-normal leading-[20px] not-italic relative shrink-0 text-[#9f9f9f] text-[14px] whitespace-nowrap" data-node-id="I411:6111;411:6053">
              May 19, 2023
            </p>
          </div>
        </div>
        <div className="content-stretch flex gap-[40px] items-center relative shrink-0" data-node-id="I411:6111;411:6054" data-name="Search">
          <div className="content-stretch flex items-center relative shrink-0" data-node-id="I411:6111;411:6055" data-name="Notification icon">
            <div className="grid-cols-[max-content] grid-rows-[max-content] inline-grid leading-[0] place-items-start relative shrink-0" data-node-id="I411:6111;411:6055;2:622">
              <div className="col-start-1 ml-0 mt-0 relative row-start-1 size-[24px]" data-node-id="I411:6111;411:6055;2:623" data-name="clarity:notification-solid-badged">
                <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgClarityNotificationSolidBadged} />
              </div>
            </div>
          </div>
          <div className="bg-white content-stretch drop-shadow-[0px_26px_13px_rgba(106,22,58,0.04)] flex gap-[170px] items-start pl-[32px] pr-[24px] py-[12px] relative rounded-[12px] shrink-0" data-node-id="I411:6111;411:6056" data-name="Search">
            <p className="[word-break:break-word]  font-normal leading-[24px] not-italic relative shrink-0 text-[#9f9f9f] text-[16px] w-[102px]" data-node-id="I411:6111;411:6056;404:5259">
              Search here
            </p>
            <Search className="overflow-clip relative shrink-0 size-[24px]" />
          </div>
        </div>
      </div>
      <div className="absolute bg-[#191919] content-stretch flex flex-col gap-[228px] items-start left-0 px-[28px] py-[48px] top-0 min-h-full" data-node-id="413:7727" data-name="Nav bar">
        <div className="content-stretch flex flex-col gap-[40px] items-start relative shrink-0" data-node-id="I413:7727;411:6376" data-name="Logo & Menu">
          <span aria-disabled="true" className="[word-break:break-word] block cursor-pointer font-['Poppins',sans-serif] leading-[0] not-italic relative shrink-0 text-[0px] text-center text-white tracking-[1.92px] w-[224px]" data-node-id="I413:7727;411:6377">
            <p className="text-[24px]">
              <span className="font-['Poppins',sans-serif] leading-[32px]">FINE</span>
              <span className="font-['Poppins',sans-serif] leading-[32px]">bank.</span>
              <span className="font-['Poppins',sans-serif] leading-[32px]">IO</span>
            </p>
          </span>
          <div className="content-stretch flex flex-col gap-[16px] items-start relative shrink-0" data-node-id="I413:7727;411:6378" data-name="Menu">
            <span aria-disabled="true" className="content-stretch cursor-pointer flex gap-[12px] items-center px-[16px] py-[12px] relative rounded-[4px] shrink-0" data-node-id="I413:7727;411:6379" data-name="Menu">
              <div className="overflow-clip relative shrink-0 size-[24px]" data-node-id="I413:7727;411:6379;2:118" data-name="Menu/Overview">
                <div className="absolute inset-[58.33%_12.5%_12.5%_58.33%]" data-node-id="I413:7727;411:6379;2:118;2:102" data-name="Vector">
                  <div className="absolute inset-[-14.29%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector3} />
                  </div>
                </div>
                <div className="absolute inset-[58.33%_58.33%_12.5%_12.5%]" data-node-id="I413:7727;411:6379;2:118;2:103" data-name="Vector">
                  <div className="absolute inset-[-14.29%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector3} />
                  </div>
                </div>
                <div className="absolute inset-[12.5%_12.5%_58.33%_58.33%]" data-node-id="I413:7727;411:6379;2:118;2:104" data-name="Vector">
                  <div className="absolute inset-[-14.29%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector3} />
                  </div>
                </div>
                <div className="absolute inset-[12.5%_58.33%_58.33%_12.5%]" data-node-id="I413:7727;411:6379;2:118;2:105" data-name="Vector">
                  <div className="absolute inset-[-14.29%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector3} />
                  </div>
                </div>
              </div>
              <p className="[word-break:break-word]  font-normal h-[24px] leading-[24px] not-italic relative shrink-0 text-[16px] text-[rgba(255,255,255,0.7)] text-left w-[156px]" data-node-id="I413:7727;411:6379;2:119">
                Overview
              </p>
            </span>
            <div className="bg-[#299d91] content-stretch flex gap-[12px] items-center px-[16px] py-[12px] relative rounded-[4px] shrink-0" data-node-id="I413:7727;411:6380" data-name="Menu">
              <div className="overflow-clip relative shrink-0 size-[24px]" data-node-id="I413:7727;411:6380;12:351" data-name="wallet">
                <div className="absolute bottom-1/2 left-[16.67%] right-[16.67%] top-[16.67%]" data-node-id="I413:7727;411:6380;12:351;2:906" data-name="Vector">
                  <div className="absolute inset-[-12.5%_-6.25%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector4} />
                  </div>
                </div>
                <div className="absolute bottom-[16.67%] left-[16.67%] right-[16.67%] top-1/4" data-node-id="I413:7727;411:6380;12:351;2:907" data-name="Vector">
                  <div className="absolute inset-[-7.14%_-6.25%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector5} />
                  </div>
                </div>
                <div className="absolute bottom-[33.33%] left-[66.67%] right-[8.33%] top-1/2" data-node-id="I413:7727;411:6380;12:351;2:908" data-name="Vector">
                  <div className="absolute inset-[-25%_-16.67%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector6} />
                  </div>
                </div>
              </div>
              <p className="[word-break:break-word]  font-semibold h-[24px] leading-[24px] not-italic relative shrink-0 text-[16px] text-white w-[156px]" data-node-id="I413:7727;411:6380;2:125">
                Balances
              </p>
            </div>
            <Link to="/transactions" className="content-stretch cursor-pointer flex gap-[12px] items-center px-[16px] py-[12px] relative rounded-[4px] shrink-0" data-node-id="I413:7727;411:6381" data-name="Menu">
              <div className="overflow-clip relative shrink-0 size-[24px]" data-node-id="I413:7727;411:6381;12:383" data-name="Transaction">
                <div className="absolute inset-[12.5%_12.5%_54.17%_70.83%]" data-node-id="I413:7727;411:6381;12:383;2:910" data-name="Vector">
                  <div className="absolute inset-[-12.5%_-25%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector7} />
                  </div>
                </div>
                <div className="absolute inset-[29.17%_12.5%_70.83%_37.5%]" data-node-id="I413:7727;411:6381;12:383;2:911" data-name="Vector">
                  <div className="absolute inset-[-1px_-8.33%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector8} />
                  </div>
                </div>
                <div className="absolute inset-[54.17%_70.83%_12.5%_12.5%]" data-node-id="I413:7727;411:6381;12:383;2:912" data-name="Vector">
                  <div className="absolute inset-[-12.5%_-25%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector9} />
                  </div>
                </div>
                <div className="absolute inset-[70.83%_37.5%_29.17%_12.5%]" data-node-id="I413:7727;411:6381;12:383;2:913" data-name="Vector">
                  <div className="absolute inset-[-1px_-8.33%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector8} />
                  </div>
                </div>
              </div>
              <p className="[word-break:break-word]  font-normal h-[24px] leading-[24px] not-italic relative shrink-0 text-[16px] text-[rgba(255,255,255,0.7)] text-left w-[156px]" data-node-id="I413:7727;411:6381;2:139">
                Transactions
              </p>
            </Link>
            <span aria-disabled="true" className="content-stretch cursor-pointer flex gap-[12px] items-center px-[16px] py-[12px] relative rounded-[4px] shrink-0" data-node-id="I413:7727;411:6382" data-name="Menu">
              <div className="overflow-clip relative shrink-0 size-[24px]" data-node-id="I413:7727;411:6382;12:388" data-name="Bill">
                <div className="absolute inset-[8.32%_8.33%_8.33%_8.33%]" data-node-id="I413:7727;411:6382;12:388;12:356" data-name="Vector">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector10} />
                </div>
              </div>
              <p className="[word-break:break-word]  font-normal h-[24px] leading-[24px] not-italic relative shrink-0 text-[16px] text-[rgba(255,255,255,0.7)] text-left w-[156px]" data-node-id="I413:7727;411:6382;2:149">
                Bills
              </p>
            </span>
            <span aria-disabled="true" className="content-stretch cursor-pointer flex gap-[12px] items-center px-[16px] py-[12px] relative rounded-[4px] shrink-0" data-node-id="I413:7727;411:6383" data-name="Menu">
              <div className="overflow-clip relative shrink-0 size-[24px]" data-node-id="I413:7727;411:6383;12:390" data-name="Expencces">
                <div className="absolute inset-[14.58%_10.42%]" data-node-id="I413:7727;411:6383;12:390;12:358" data-name="Group">
                  <div className="absolute inset-[-5.88%_-5.26%]">
                    <img alt="" className="block max-w-none size-full" src={imgGroup} />
                  </div>
                </div>
              </div>
              <div className="[word-break:break-word]  font-normal h-[24px] leading-[0] not-italic relative shrink-0 text-[16px] text-[rgba(255,255,255,0.7)] text-left w-[156px]" data-node-id="I413:7727;411:6383;2:159">
                <p className="leading-[24px] mb-0">Expenses</p>
                <p className="leading-[24px]">{'\u200B'}</p>
              </div>
            </span>
            <span aria-disabled="true" className="content-stretch cursor-pointer flex gap-[12px] items-center px-[16px] py-[12px] relative rounded-[4px] shrink-0" data-node-id="I413:7727;411:6384" data-name="Menu">
              <div className="overflow-clip relative shrink-0 size-[24px]" data-node-id="I413:7727;411:6384;12:396" data-name="Goal">
                <div className="absolute inset-[8.33%]" data-node-id="I413:7727;411:6384;12:396;2:915" data-name="Vector">
                  <div className="absolute inset-[-5%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector11} />
                  </div>
                </div>
                <div className="absolute bottom-1/2 left-3/4 right-[8.33%] top-1/2" data-node-id="I413:7727;411:6384;12:396;2:916" data-name="Vector">
                  <div className="absolute inset-[-1px_-25%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector12} />
                  </div>
                </div>
                <div className="absolute bottom-1/2 left-[8.33%] right-3/4 top-1/2" data-node-id="I413:7727;411:6384;12:396;2:917" data-name="Vector">
                  <div className="absolute inset-[-1px_-25%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector12} />
                  </div>
                </div>
                <div className="absolute bottom-3/4 left-1/2 right-1/2 top-[8.33%]" data-node-id="I413:7727;411:6384;12:396;2:918" data-name="Vector">
                  <div className="absolute inset-[-25%_-1px]">
                    <img alt="" className="block max-w-none size-full" src={imgVector13} />
                  </div>
                </div>
                <div className="absolute bottom-[8.33%] left-1/2 right-1/2 top-3/4" data-node-id="I413:7727;411:6384;12:396;2:919" data-name="Vector">
                  <div className="absolute inset-[-25%_-1px]">
                    <img alt="" className="block max-w-none size-full" src={imgVector13} />
                  </div>
                </div>
              </div>
              <p className="[word-break:break-word]  font-normal h-[24px] leading-[24px] not-italic relative shrink-0 text-[16px] text-[rgba(255,255,255,0.7)] text-left w-[156px]" data-node-id="I413:7727;411:6384;2:169">
                Goals
              </p>
            </span>
            <span aria-disabled="true" className="content-stretch cursor-pointer flex gap-[12px] items-center px-[16px] py-[12px] relative rounded-[4px] shrink-0" data-node-id="I413:7727;411:6385" data-name="Menu">
              <div className="overflow-clip relative shrink-0 size-[24px]" data-node-id="I413:7727;411:6385;12:402" data-name="Menu/Settings">
                <div className="absolute inset-[40.22%]" data-node-id="I413:7727;411:6385;12:402;2:88" data-name="Vector">
                  <div className="absolute inset-[-21.31%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector14} />
                  </div>
                </div>
                <div className="absolute inset-[12.5%]" data-node-id="I413:7727;411:6385;12:402;2:89" data-name="Vector">
                  <div className="absolute inset-[-5.56%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector15} />
                  </div>
                </div>
              </div>
              <p className="[word-break:break-word]  font-normal h-[24px] leading-[24px] not-italic relative shrink-0 text-[16px] text-[rgba(255,255,255,0.7)] text-left w-[156px]" data-node-id="I413:7727;411:6385;2:179">
                Settings
              </p>
            </span>
          </div>
        </div>
        <div className="content-stretch cursor-pointer flex flex-col gap-[44px] items-start relative shrink-0" data-node-id="I413:7727;411:6386" data-name="Footer">
          <button type="button" onClick={logout} className="bg-[rgba(255,255,255,0.08)] content-stretch flex gap-[12px] items-center opacity-75 px-[16px] py-[12px] relative rounded-[4px] shrink-0" data-node-id="I413:7727;411:6387" data-name="Logout Button">
            <div className="content-stretch flex items-center relative shrink-0 size-[24px]" data-node-id="I413:7727;411:6387;13:631" data-name="Icon">
              <div className="overflow-clip relative shrink-0 size-[20px]" data-node-id="I413:7727;411:6387;13:631;13:626" data-name="Logout">
                <div className="absolute inset-[29.17%_37.5%_29.17%_41.67%]" data-node-id="I413:7727;411:6387;13:631;13:626;9:888" data-name="Vector">
                  <div className="absolute inset-[-12%_-24%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector16} />
                  </div>
                </div>
                <div className="absolute bottom-1/2 left-[12.5%] right-[37.5%] top-1/2" data-node-id="I413:7727;411:6387;13:631;13:626;9:889" data-name="Vector">
                  <div className="absolute inset-[-1px_-10%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector17} />
                  </div>
                </div>
                <div className="absolute inset-[12.5%_12.5%_12.5%_62.5%]" data-node-id="I413:7727;411:6387;13:631;13:626;9:890" data-name="Vector">
                  <div className="absolute inset-[-6.67%_-20%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector18} />
                  </div>
                </div>
              </div>
            </div>
            <p className="[word-break:break-word]  font-semibold h-[24px] leading-[24px] not-italic relative shrink-0 text-[16px] text-left text-white w-[156px]" data-node-id="I413:7727;411:6387;13:638">
              Logout
            </p>
          </button>
          <span aria-disabled="true" className="border-[rgba(255,255,255,0.08)] border-solid border-t content-stretch flex gap-[32px] items-center py-[32px] relative shrink-0" data-node-id="I413:7727;411:6388" data-name="Profile">
            <div className="content-stretch flex gap-[16px] items-center relative shrink-0" data-node-id="I413:7727;411:6388;403:5380" data-name="Name & Picture">
              <div className="relative shrink-0 size-[32px]" data-node-id="I413:7727;411:6388;403:5381" data-name="Image">
                <img alt="" className="absolute block inset-0 max-w-none size-full" height="32" src={imgImage} width="32" />
              </div>
              <div className="[word-break:break-word] content-stretch flex flex-col items-start not-italic relative shrink-0 text-left" data-node-id="I413:7727;411:6388;403:5382" data-name="Name">
                <p className=" font-semibold leading-[24px] relative shrink-0 text-[16px] text-white w-[140px]" data-node-id="I413:7727;411:6388;403:5383">
                  {user?.fullName ?? 'Application user'}
                </p>
                <p className=" font-normal leading-[16px] relative shrink-0 text-[12px] text-[rgba(255,255,255,0.7)] whitespace-nowrap" data-node-id="I413:7727;411:6388;403:5384">
                  View profile
                </p>
              </div>
            </div>
            <div className="h-[20px] relative shrink-0 w-[4px]" data-node-id="I413:7727;411:6388;403:5385" data-name="Icon">
              <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIcon} />
            </div>
          </span>
        </div>
      </div>
      {accountToDelete && <DeleteAccountModal account={accountToDelete} onCancel={() => setAccountToDelete(null)} onUnauthorized={() => { setAccountToDelete(null); logout(); navigate('/login', { replace: true, state: { sessionMessage: 'Please log in again.' } }); }} onDeleted={(deletedAccountId) => {
        setAccounts((current) => current.filter((account) => account.id !== deletedAccountId));
        if (selectedAccount?.id === deletedAccountId) { setSelectedAccount(null); setIsEditing(false); }
        setAccountToDelete(null);
        setSuccessMessage('Account successfully deleted.');
      }} />}
    </div>
  );
}

function AccountCard({ account, index, onDetails, onRemove }: { account: BankAccount; index: number; onDetails: () => void; onRemove: () => void }) {
  return (
<div className="bg-white content-stretch drop-shadow-[0px_20px_12.5px_rgba(76,103,100,0.1)] flex flex-col gap-[16px] items-start p-[24px] relative rounded-[8px] shrink-0" data-node-id={cardNodeIds[index] ?? `account-${account.id}`} data-name="Account Type">
              <div className="border-[rgba(210,210,210,0.25)] border-b border-solid content-stretch flex h-[44px] items-center justify-between pb-[12px] relative shrink-0 w-[304px]" data-node-id="I410:5376;410:5321" data-name="Header">
                <p className="[word-break:break-word] capitalize  font-bold leading-[24px] not-italic relative shrink-0 text-[#878787] text-[16px] whitespace-nowrap" data-node-id="I410:5376;410:5322">
                  {account.account_type}
                </p>
                <div className="content-stretch flex gap-[4px] items-center relative shrink-0" data-node-id="I410:5376;410:5351" data-name="Type">
                  <div className="content-stretch flex items-start py-[8px] relative shrink-0" data-node-id="I410:5376;410:5445">
                    <p className="[word-break:break-word]  font-medium leading-[16px] not-italic relative shrink-0 text-[#666] text-[12px] text-right max-w-[160px] truncate" data-node-id="I410:5376;410:5350">
                      {account.bank_name}
                    </p>
                  </div>
                  <div className="content-stretch flex items-center relative shrink-0" data-node-id="I410:5376;410:5323" data-name="Icon">
                    {index === 0 ? <Mastercard className="h-[32px] overflow-clip relative shrink-0 w-[48px]" /> : index === 1 ? <div className="relative h-8 w-12"><img alt="" src={imgVisaLogo1} className="absolute left-px top-[9px] h-[14px] w-[46px]" /></div> : null}
                  </div>
                </div>
              </div>
              <div className="content-stretch flex flex-col gap-[24px] items-start relative shrink-0" data-node-id="I410:5376;410:5330" data-name="Content">
                <div className="[word-break:break-word] content-stretch flex flex-col gap-[16px] items-start not-italic relative shrink-0" data-node-id="I410:5376;410:5349" data-name="Account Details">
                  <div className="content-stretch flex flex-col gap-[4px] items-start relative shrink-0" data-node-id="I410:5376;410:5331" data-name="Account Number">
                    <p className="capitalize  font-semibold leading-[28px] relative shrink-0 text-[#191919] text-[20px] w-[304px] whitespace-pre-wrap" data-node-id="I410:5376;410:5332">{`**** **** **** ${account.account_number_last_4}`}</p>
                    <p className=" font-normal leading-[20px] relative shrink-0 text-[#9f9f9f] text-[14px] w-[304px] truncate" data-node-id="I410:5376;410:5333">
                      Account Number · {account.branch_name}
                    </p>
                  </div>
                  <div className="content-stretch flex flex-col gap-[4px] items-start relative shrink-0" data-node-id="I410:5376;410:5335" data-name="Total amount">
                    <p className="capitalize  font-semibold leading-[28px] relative shrink-0 text-[#191919] text-[20px] w-[125px]" data-node-id="I410:5376;410:5336">
                      {formatBalance(account.balance)}
                    </p>
                    <p className=" font-normal leading-[20px] relative shrink-0 text-[#9f9f9f] text-[14px] w-[125px]" data-node-id="I410:5376;410:5337">
                      Total amount
                    </p>
                  </div>
                </div>
                <div className="content-stretch flex items-center justify-between relative shrink-0 w-[303px]" data-node-id="I410:5376;410:5338" data-name="Footer">
                  <button type="button" onClick={onRemove} className="[word-break:break-word] rounded text-left font-normal leading-[24px] not-italic relative shrink-0 text-red-700 text-[16px] w-[116px] focus:outline-none focus:ring-2 focus:ring-red-700 focus:ring-offset-2" aria-label={`Remove ${account.bank_name} account ending ${account.account_number_last_4}`} data-node-id="I410:5376;410:5340">
                    Remove
                  </button>
                  <button type="button" onClick={onDetails} aria-label={`View details for ${account.bank_name} account ending ${account.account_number_last_4}`} className="bg-[#299d91] content-stretch cursor-pointer flex gap-[8px] items-center px-[20px] py-[8px] relative rounded-[4px] shrink-0 focus:outline-none focus:ring-2 focus:ring-[#299d91] focus:ring-offset-2" data-node-id="I410:5376;410:5339" data-name="Button">
                    <p className="[word-break:break-word] capitalize  font-medium leading-[20px] not-italic relative shrink-0 text-[14px] text-left text-white whitespace-nowrap" data-node-id="I410:5376;410:5339;36:1180">
                      Details
                    </p>
                    <div className="overflow-clip relative shrink-0 size-[16px]" data-node-id="I410:5376;410:5339;36:1181" data-name="chevron-right">
                      <div className="absolute bottom-1/4 left-[37.5%] right-[37.5%] top-1/4" data-node-id="I410:5376;410:5339;36:1181;14:744" data-name="Vector">
                        <div className="absolute inset-[-9.38%_-18.75%]">
                          <img alt="" className="block max-w-none size-full" src={imgVector2} />
                        </div>
                      </div>
                    </div>
                  </button>
                </div>
              </div>
            </div>
  );
}

function AccountDetailsPanel({ account, onBack, onEdit, onDelete }: { account: BankAccount; onBack: () => void; onEdit: () => void; onDelete: () => void }) {
  return (
    <section className="max-w-3xl rounded-xl bg-white p-8 shadow-[0_20px_40px_rgba(76,103,100,0.12)]" aria-labelledby="account-details-title">
      <button type="button" onClick={onBack} className="mb-6 rounded text-sm font-semibold text-[#299d91] focus:outline-none focus:ring-2 focus:ring-[#299d91] focus:ring-offset-2">← Back to accounts</button>
      <p className="mb-2 text-sm font-semibold uppercase tracking-wide text-[#299d91]">Account details</p>
      <h2 id="account-details-title" className="text-3xl font-bold text-[#191919]">{account.bank_name}</h2>
      <dl className="mt-8 grid gap-5 sm:grid-cols-2">
        <Detail label="Account Type" value={account.account_type} />
        <Detail label="Branch" value={account.branch_name || '—'} />
        <Detail label="Account Number" value={`•••• ${account.account_number_last_4}`} />
        <Detail label="Current Balance" value={`${new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 4 }).format(account.balance)} VND`} />
      </dl>
      <div className="mt-8 flex justify-end gap-3">
        <button type="button" onClick={onDelete} className="min-h-12 rounded-md border border-red-700 px-6 py-3 font-bold text-red-700 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-700 focus:ring-offset-2">Delete</button>
        <button type="button" onClick={onEdit} className="min-h-12 rounded-md bg-[#299d91] px-6 py-3 font-bold text-white hover:bg-[#237f75] focus:outline-none focus:ring-2 focus:ring-[#299d91] focus:ring-offset-2">Edit</button>
      </div>
    </section>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-sm font-semibold text-[#878787]">{label}</dt><dd className="mt-1 text-lg font-semibold text-[#191919]">{value}</dd></div>;
}

function AddAccountCard() {
  return (
<div className="bg-white content-stretch drop-shadow-[0px_20px_12.5px_rgba(76,103,100,0.1)] flex flex-col items-center justify-center pb-[88px] pt-[100px] px-[24px] relative rounded-[8px] shrink-0 w-[352px]" data-node-id="410:5516" data-name="Add Account">
              <div className="content-stretch flex flex-col gap-[4px] items-start relative shrink-0" data-node-id="410:5517" data-name="Button">
                <Link to="/accounts/new" className="bg-[#299d91] content-stretch flex items-center px-[32px] py-[12px] relative rounded-[4px] shrink-0" data-node-id="410:5539" data-name="Button Big">
                  <p className="[word-break:break-word] capitalize  font-bold leading-[24px] not-italic relative shrink-0 text-[16px] text-center text-white w-[144px]" data-node-id="I410:5539;410:5535">
                    Add accounts
                  </p>
                </Link>
                <div className="content-stretch flex items-start px-[24px] py-[12px] relative shrink-0" data-node-id="410:5545" aria-disabled="true">
                  <p className="[word-break:break-word]  font-medium leading-[24px] not-italic relative shrink-0 text-[#9f9f9f] text-[16px] text-center w-[160px]" data-node-id="410:5530">
                    Edit Accounts
                  </p>
                </div>
              </div>
            </div>
  );
}
