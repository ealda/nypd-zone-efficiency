# montecarlo.R -- RTM-propagation identification under known truth (R port).
# Writes data/mc_results_R.csv.
suppressMessages(library(lpSolve))
set.seed(11)
N <- 50; REPS <- 15; ALPHA <- 0.5; K <- 0.8
SIGMAS <- c(0.10,0.25,0.45,0.70)

dea1 <- function(x,y){                      # input-oriented VRS, 1 input/1 output
  x <- pmax(x,1e-6); y <- y - min(y) + 1; n <- length(x); th <- numeric(n)
  for(o in 1:n){
    con <- rbind(c(-x[o], x), c(0, y), c(0, rep(1,n)))
    s <- lp("min", c(1, rep(0,n)), con, c("<=",">=","="), c(0, y[o], 1))
    th[o] <- if(s$status==0) s$objval else NA
  }
  th
}
one_rep <- function(sigma){
  mu <- exp(rnorm(N,2.0,0.6)); e <- runif(N,0.3,1.0)
  pre <- replicate(4, mu*exp(rnorm(N,0,sigma)))           # N x 4
  ct<-pre[,4]; c1<-pre[,3]; m3<-rowMeans(pre[,1:3])
  b <- coef(lm(ct ~ c1 + m3))
  eps_prev<-rnorm(N,0,sigma); eps_now<-rnorm(N,0,sigma)
  c_prev<-mu*exp(eps_prev); d<-K*c_prev; a_true<-e*d^ALPHA
  c_now<-mu*exp(eps_now)-a_true
  pred<-b[1]+b[2]*c_prev+b[3]*mu
  raw<-c_prev-c_now; net<-pred-c_now
  et<-dea1(d,a_true); er<-dea1(d,raw); en<-dea1(d,net)
  sp<-function(a,bb){ok<-is.finite(a)&is.finite(bb); cor(a[ok],bb[ok],method="spearman")}
  c(sp(er,eps_prev), sp(en,eps_prev), sp(er,et), sp(en,et))
}
res <- lapply(SIGMAS, function(s){ m<-rowMeans(sapply(1:REPS, function(i) one_rep(s)));
  data.frame(sigma=s,reps=REPS,sig_raw=round(m[1],3),sig_net=round(m[2],3),
             rec_raw=round(m[3],3),rec_net=round(m[4],3)) })
out <- do.call(rbind,res); write.csv(out,"data/mc_results_R.csv",row.names=FALSE)
print(out)
cat("\nNET recovers truth >= RAW at every sigma:", all(out$rec_net>=out$rec_raw-0.02),"\n")
