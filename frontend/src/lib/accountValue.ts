import type { Account } from "@/lib/api";

/**
 * The one number every screen shows for an account: its current value, computed in the Lambda
 * (holdings at today's prices plus cash). The account list, the Holdings picker and the Accounts
 * total all read it here, so they cannot disagree. A new empty account falls back to its balance.
 */
export const accountValue = (account: Pick<Account, "value_cad" | "balance">): number =>
  account.value_cad ?? account.balance ?? 0;

/** An investor's total across their accounts: the sum of the account values. */
export const totalAccountValue = (accounts: Array<Pick<Account, "value_cad" | "balance">>): number =>
  accounts.reduce((sum, account) => sum + accountValue(account), 0);
