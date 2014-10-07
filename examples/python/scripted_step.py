#############################################################################
# This script contains two trivial examples of simple "scripted step" classes.
# To fully understand how the lldb "Thread Plan" architecture works, read the
# comments at the beginning of ThreadPlan.h in the lldb sources.  The python
# interface is a reduced version of the full internal mechanism, but captures
# most of the power with a much simpler interface.
#
# But I'll attempt a brief summary here.  
# Stepping in lldb is done independently for each thread.  Moreover, the stepping
# operations are stackable.  So for instance if you did a "step over", and in 
# the course of stepping over you hit a breakpoint, stopped and stepped again,
# the first "step-over" would be suspended, and the new step operation would
# be enqueued.  Then if that step over caused the program to hit another breakpoint,
# lldb would again suspend the second step and return control to the user, so
# now there are two pending step overs.  Etc. with all the other stepping 
# operations.  Then if you hit "continue" the bottom-most step-over would complete, 
# and another continue would complete the first "step-over".
#
# lldb represents this system with a stack of "Thread Plans".  Each time a new
# stepping operation is requested, a new plan is pushed on the stack.  When the
# operation completes, it is pushed off the stack.
#
# The bottom-most plan in the stack is the immediate controller of stepping,
# most importantly, when the process resumes, the bottom most plan will get
# asked whether to set the program running freely, or to instruction-single-step
# the current thread.  In the scripted interface, you indicate this by returning
# False or True respectively from the should_step method.
#
# Each time the process stops the thread plan stack for each thread that stopped 
# "for a reason", Ii.e. a single-step completed on that thread, or a breakpoint
# was hit), is queried to determine how to proceed, starting from the most 
# recently pushed plan, in two stages:
#
# 1) Each plan is asked if it "explains" the stop.  The first plan to claim the
#    stop wins.  In scripted Thread Plans, this is done by returning True from
#    the "explains_stop method.  This is how, for instance, control is returned
#    to the User when the "step-over" plan hits a breakpoint.  The step-over 
#    plan doesn't explain the breakpoint stop, so it returns false, and the 
#    breakpoint hit is propagated up the stack to the "base" thread plan, which
#    is the one that handles random breakpoint hits.
#
# 2) Then the plan that won the first round is asked if the process should stop.
#    This is done in the "should_stop" method.  The scripted plans actually do
#    three jobs in should_stop:
#      a) They determine if they have completed their job or not.  If they have
#         they indicate that by calling SetPlanComplete on their thread plan.
#      b) They decide whether they want to return control to the user or not.
#         They do this by returning True or False respectively.
#      c) If they are not done, they set up whatever machinery they will use
#         the next time the thread continues.
#
#    Note that deciding to return control to the user, and deciding your plan
#    is done, are orthgonal operations.  You could set up the next phase of 
#    stepping, and then return True from should_stop, and when the user next
#    "continued" the process your plan would resume control.  Of course, the
#    user might also "step-over" or some other operation that would push a 
#    different plan, which would take control till it was done.
#
#    One other detail you should be aware of, if the plan below you on the
#    stack was done, then it will be popped and the next plan will take control
#    and its "should_stop" will be called.
#
#    Note also, there should be another method called when your plan is popped,
#    to allow you to do whatever cleanup is required.  I haven't gotten to that
#    yet.  For now you should do that at the same time you mark your plan complete.
#
# Both examples show stepping through an address range for 20 bytes from the
# current PC.  The first one does it by single stepping and checking a condition.
# It doesn't, however handle the case where you step into another frame while
# still in the current range in the starting frame.  
#
# That is better handled in the second example by using the built-in StepOverRange
# thread plan.
#
# To use these stepping modes, you would do:
#
#     (lldb) command script import scripted_step.py
#     (lldb) thread step-scripted -C scripted_step.SimpleStep
# or
#
#     (lldb) thread step-scripted -C scripted_step.StepWithPlan

import lldb

class SimpleStep:
    def __init__ (self, thread_plan, dict):
        self.thread_plan = thread_plan
        self.start_address = thread_plan.GetThread().GetFrameAtIndex(0).GetPC()
        
    def explains_stop (self, event):
        # We are stepping, so if we stop for any other reason, it isn't
        # because of us.
        if self.thread_plan.GetThread().GetStopReason()== lldb.eStopReasonTrace:
            return True
        else:
            return False
        
    def should_stop (self, event):
        cur_pc = self.thread_plan.GetThread().GetFrameAtIndex(0).GetPC()
        
        if cur_pc < self.start_address or cur_pc >= self.start_address + 20:
            self.thread_plan.SetPlanComplete(True)
            return True
        else:
            return False

    def should_step (self):
        return True

class StepWithPlan:
    def__init__ (self,thread_plan, dict):
        self.thread_plan = thread_plan
        self.start_address = thread_plan.GetThread().GetFrameAtIndex(0).GetPCAddress()
        self.step_thread_plan =thread_plan.QueueThreadPlanForStepOverRange(self.start_address, 20);

    def explains_stop (self, event):
        # Since all I'm doing is running a plan, I will only ever get askedthis
        # if myplan doesn't explain the stop, and in that caseI don'teither.
        return False

    def should_stop (self, event):
        if self.step_thread_plan.IsPlanComplete():
            self.thread_plan.SetPlanComplete(True)
            return True
        else:
            return False

    def should_step (self):
        return False
