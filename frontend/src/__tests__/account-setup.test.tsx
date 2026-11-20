import {afterEach,beforeEach,describe,expect,it,vi} from "vitest";
import {cleanup,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InvitationPage from "@/app/accept-invitation/page";
import ForgotPasswordPage from "@/app/forgot-password/page";
import {api} from "@/lib/api";
import {authService} from "@/services/auth";
const {replace,refresh}=vi.hoisted(()=>({replace:vi.fn(),refresh:vi.fn()}));
vi.mock("next/navigation",()=>({useRouter:()=>({replace}),useSearchParams:()=>new URLSearchParams("token=private-link")}));
vi.mock("@/hooks/useAuth",()=>({useAuth:()=>({session:null,refreshSession:refresh,logout:vi.fn()})}));
vi.mock("@/lib/api",()=>({api:{post:vi.fn()}}));
vi.mock("@/services/auth",()=>({authService:{completePortalInvitation:vi.fn(),requestPasswordReset:vi.fn()}}));
beforeEach(()=>{vi.clearAllMocks();vi.mocked(api.post).mockResolvedValue({facility:"Test clinic",email_masked:"p***",existing_account:false,used:false});});
afterEach(cleanup);
describe("Private account setup",()=>{
 it("creates a patient password then refreshes the actual session",async()=>{
  const u=userEvent.setup();render(<InvitationPage/>);
  await u.type(await screen.findByLabelText("Your full name"),"Test Patient");
  await u.type(screen.getByLabelText("Create your password"),"MyPrivatePass123!");
  await u.type(screen.getByLabelText("Confirm password"),"MyPrivatePass123!");
  await u.click(screen.getByRole("button",{name:"Set up my portal"}));
  await waitFor(()=>expect(authService.completePortalInvitation).toHaveBeenCalledWith({token:"private-link",new_password:"MyPrivatePass123!",full_name:"Test Patient"}));
  expect(refresh).toHaveBeenCalled();expect(replace).toHaveBeenCalledWith("/portal");
 });
 it("keeps existing passwords and retains the invitation through sign-in",async()=>{
  vi.mocked(api.post).mockResolvedValue({facility:"Test clinic",email_masked:"p***",existing_account:true,used:false});render(<InvitationPage/>);
  expect(await screen.findByRole("link",{name:"Sign in to accept"})).toHaveAttribute("href","/login?next=%2Faccept-invitation%3Ftoken%3Dprivate-link");
  expect(screen.queryByLabelText("Create your password")).not.toBeInTheDocument();
 });
 it("shows a generic recovery acknowledgement without exposing a token",async()=>{
  vi.mocked(authService.requestPasswordReset).mockResolvedValue({accepted:true,message:"If the account exists, a reset link will be sent."});
  const u=userEvent.setup();render(<ForgotPasswordPage/>);
  await u.type(screen.getByRole("textbox"),"patient@example.com");await u.click(screen.getByRole("button",{name:"Request Reset"}));
  expect(await screen.findByText("If the account exists, a reset link will be sent.")).toBeInTheDocument();
  expect(screen.queryByText(/Dev Token/)).not.toBeInTheDocument();
 });
});
